#!/usr/bin/env python3
"""Clasifica liniile unui ENUNT in cod/text si reindenteaza blocurile de cod,
la momentul generarii (nu in JS la runtime), pentru randare consistenta."""
import re

# --- clasificare linie: cod vs proza -------------------------------------------------

CODE_PATTERNS = [
    r'[;{}]',
    r'^(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|UPDATE|INSERT|DELETE|CREATE|DROP|ALTER|TRUNCATE|GRANT|REVOKE)\b',
    r'^(BEGIN|END\b|DECLARE|EXCEPTION|LOOP\b|EXIT\b|ELSIF\b|ELSE\b|RETURN\b|WHEN\b|THEN\s*$)',
    r'^(SET\s|VALUES\b|INTO\b)',
    r'^(OPEN\s|FETCH\s|CLOSE\s|EXECUTE\s|PROCEDURE\s|FUNCTION\s|CURSOR\s|TRIGGER\s|PRAGMA\s|COMMIT\b|ROLLBACK\b|SAVEPOINT\b)',
    r'^(UNION(\s+ALL)?|MINUS|INTERSECT)\s*$',
    r'^FOR\s+\w+\s+IN\b',
    r'^WHILE\b.*\bLOOP\b',
    r'^(IS|AS)\s*$',
    r'^(IF\b|IF\()',
    r'^#include',
    r'^(int|void|char|float|double|long|short|struct|class|enum|union|typedef|template|namespace)\s',
    r'^template\s*<',
    r'^(public|private|protected)\s*:',
    r'^(printf|scanf|malloc|free|new\s|delete\b|sizeof|friend\s|operator|virtual\s)\b',
    r'^(case\s.+:|default\s*:)',
    r'^do\s*\{?\s*$',
    r'^for\s*\(', r'^while\s*\(', r'^switch\s*\(',
    r'^\.\.\.$',
    r'^/$',                                              # terminator bloc PL/SQL (SQL*Plus)
    r'^(AND|OR)\b',
    r'^\([^)]*\b(SELECT|IN|OUT)\b',
    r'^[A-Za-z_][\w:.<>*&]*(\s+[A-Za-z_]\w*)?\s*\([^()]*\)\s*\{?\s*;?\s*$',  # semnatura de functie (ex: "g(int x)", "A f()")
]
CODE_RE = re.compile('|'.join(f'(?:{p})' for p in CODE_PATTERNS), re.IGNORECASE)

# etichete scurte de tip "I1." "I2." "A2." care preced o varianta de cod - se alatura codului
LABEL_RE = re.compile(r'^[A-Za-z]{1,3}\d{0,2}\.$')


TERMINATOR_CHARS = (';', '}', '/')
PROSE_END_CHARS = ('.', '?', ':')


def classify_lines(lines):
    """Intoarce o lista de 'code'/'text' per linie (liniile goale raman None).
    Regula principala: daca linia anterioara e cod si NU se termina cu un
    terminator de instructiune (; } /) sau cu punctuatie de final de fraza
    (. ? :), linia curenta e o continuare a aceluiasi cod (interogare/bloc
    infasurat pe mai multe randuri), indiferent daca se potriveste cu vreun
    cuvant cheie. Aceasta prinde robust AND/OR/JOIN/BEFORE/AFTER/friend/
    template si orice alta continuare, fara o lista infinita de cuvinte cheie."""
    types = []
    prev_was_open_code = False
    for line in lines:
        s = line.strip()
        if not s:
            types.append(None)
            prev_was_open_code = False
            continue
        if prev_was_open_code or CODE_RE.search(s):
            types.append('code')
        else:
            types.append('text')
        if types[-1] == 'code':
            prev_was_open_code = not s.endswith(TERMINATOR_CHARS) and not s.endswith(PROSE_END_CHARS)
        else:
            prev_was_open_code = False
    # etichetele scurte tip "I1." se alatura codului daca sunt urmate de cod
    for i, s in enumerate(lines):
        st = s.strip()
        if types[i] == 'text' and LABEL_RE.match(st):
            nxt = next((types[j] for j in range(i + 1, len(lines)) if types[j] is not None), None)
            if nxt == 'code':
                types[i] = 'code'
    return types


def group_enunt(text):
    """Grupeaza enuntul in segmente {'type': 'code'|'text', 'lines': [...]}.
    O linie goala intre doua linii de ACELASI tip se pastreaza in interiorul
    grupului (util pt spatiere intre definitii de clase); o linie goala intre
    tipuri DIFERITE marcheaza o tranzitie reala si se ignora."""
    raw_lines = text.split('\n')
    types = classify_lines(raw_lines)
    groups = []
    cur = None
    pending_blanks = 0
    for raw, t in zip(raw_lines, types):
        line = raw.strip()
        if t is None:
            pending_blanks += 1
            continue
        if cur and cur['type'] == t:
            cur['lines'].extend([''] * pending_blanks)
            cur['lines'].append(line)
        else:
            cur = {'type': t, 'lines': [line]}
            groups.append(cur)
        pending_blanks = 0
    return groups


# --- reindentare bloc de cod ----------------------------------------------------------

# dedenteaza PERMANENT (inchide un bloc real): afecteaza adancimea liniilor urmatoare
HARD_DEDENT_RE = re.compile(r'^(END\b|ELSE\b|ELSIF\b|WHEN\b|EXCEPTION\b)', re.IGNORECASE)
# dedenteaza doar liniei curente (eticheta), adancimea urmatoarelor linii ramane neschimbata
SOFT_DEDENT_RE = re.compile(
    r'^(default\s*:|case\s.+:|private\s*:|public\s*:|protected\s*:)', re.IGNORECASE
)
# linii care nu schimba adancimea liniei curente, dar deschid un nivel pt urmatoarele
OPENS_AFTER_RE = re.compile(
    r'(\bBEGIN\b\s*$|\bLOOP\b\s*$|\bTHEN\b\s*$|\bIS\b\s*$|\bAS\b\s*$|\bCASE\b\s*$|\bDECLARE\b\s*$|\bELSE\b\s*$|\bELSIF\b.*\bTHEN\b\s*$|\bWHEN\b.*\bTHEN\b\s*$|\bEXCEPTION\b\s*$)',
    re.IGNORECASE,
)

BEGIN_RE = re.compile(r'^BEGIN\s*$', re.IGNORECASE)
DECLARE_OPENER_RE = re.compile(r'\bDECLARE\s*$', re.IGNORECASE)


def reindent_code(lines, unit='    '):
    """Reindenteaza un bloc de cod pe baza acoladelor (C/C++) si a cuvintelor cheie PL/SQL."""
    out = []
    depth = 0
    after_declare = False  # BEGIN care urmeaza direct dupa DECLARE se aliniaza cu el, nu se indenteaza suplimentar
    for raw in lines:
        s = raw.strip()
        if s == '':
            out.append('')
            continue

        starts_close_brace = s.startswith('}')
        is_begin = bool(BEGIN_RE.match(s))
        is_hard_dedent = starts_close_brace or bool(HARD_DEDENT_RE.match(s))
        is_soft_dedent = bool(SOFT_DEDENT_RE.match(s)) or (is_begin and after_declare)

        print_depth = max(0, depth - 1) if (is_hard_dedent or is_soft_dedent) else depth
        out.append(unit * print_depth + s)

        if is_hard_dedent:
            depth = max(0, depth - 1)
            if not starts_close_brace and OPENS_AFTER_RE.search(s):
                depth += 1  # ex: ELSE/ELSIF...THEN redeschide un bloc dupa ce l-a inchis pe precedentul
        brace_delta = s.count('{') - s.count('}')
        if brace_delta:
            depth += brace_delta
        elif is_begin and not after_declare:
            depth += 1  # BEGIN fara DECLARE inainte deschide propriul nivel
        elif not is_hard_dedent and not is_soft_dedent and OPENS_AFTER_RE.search(s):
            depth += 1
        depth = max(0, depth)
        if is_begin:
            after_declare = False  # BEGIN consuma starea de "dupa declare"
        elif DECLARE_OPENER_RE.search(s):
            after_declare = True   # ramane True peste orice numar de declaratii de variabile
    return out


# --- randare HTML (baked la generare, nu la runtime in JS) ---------------------------

def escape_html(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def render_enunt_html(text):
    """Grupeaza + reindenteaza + escapeaza + produce HTML-ul final gata de inserat."""
    groups = group_enunt(text)
    parts = []
    for g in groups:
        if g['type'] == 'code':
            code_lines = reindent_code(g['lines'])
            parts.append('<pre class="code">' + escape_html('\n'.join(code_lines)) + '</pre>')
        else:
            parts.append('<p>' + escape_html(' '.join(g['lines'])) + '</p>')
    return ''.join(parts)
