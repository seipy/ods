#!/usr/bin/python3
import sys
import os
import re

g_labels = set()

def get_arg(s, i):
    """Match the brace starting at position i-1 with its corresponding brace"""
    if s[i] == '[':
        while s[i] != ']': i += 1
        i += 1
    depth = 0
    for j in range(i, len(s)):
        if s[j] == '{': depth += 1
        if s[j] == '}': depth -= 1
        if depth == 0: return i+1, j
    return i+1, len(s)

def merge_lines(tex):
    """Merge lines in a latex file"""
    lines = [line.strip() for line in tex.splitlines()]
    out=''
    for i in range(len(lines)-1):
        if lines[i] == '' or lines[i+1] == '':
            sep = '\n'
        else:
            sep = ' '
        out += lines[i] + sep
    return out

def split_paragraphs(tex):
    """Identify paragraph breaks"""
    lines = [line.strip() for line in tex.splitlines()]
    out=''
    for i in range(len(lines)-1):
        if lines[i] == '' and lines[i+1] != '':
            lines[i] += "<p>"
    return "\n".join(lines)

def preprocess_hashes(tex):
    """Preprocess hashes

    Right now all we do is protect % inside hashes
    """
    pattern = r'#(.*?)#'
    m = re.search(pattern, tex, re.M|re.S)
    while m:
        replacement = '\0' + re.sub('%', r'\%', m.group(1)) + '\1'
        tex = tex.replace(m.group(0), replacement)
        m = re.search(pattern, tex, re.M|re.S)
    return re.sub('[\0\1]', '#', tex)

def process_hash_interior(txt):
    return "$\mathtt{" + re.sub(r'\&', '&amp;', txt) + "}$"

def process_nonmath_hashes(tex):
    """Process the hashes

    Call this after hashes within math environments have already been dealt with
    """
    pattern = r'#(.*?)#'
    m = re.search(pattern, tex, re.M|re.S)
    while m:
        code = "$\mathtt{" + m.group(1) + "}$"
        code = re.sub(r'\&', r'\&', code)
        tex = tex.replace(m.group(0), code)
        m = re.search(pattern, tex, re.M|re.S)
    return re.sub('[\0\1]', ' ', tex)

def process_math_hashes(subtex):
    """Process the hashes

    Call this after hashes within math environments have already been dealt with
    """
    pattern = r'#(.*?)#'
    m = re.search(pattern, subtex, re.M|re.S)
    while m:
        inner = re.sub(r'\&', r'\&', m.group(1))
        inner = r'\mathtt{' + inner + '}'
        subtex = subtex[:m.start()] + inner + subtex[m.end():]
        m = re.search(pattern, subtex, re.M|re.S)
    return re.sub('[\0\1]', ' ', subtex)


def process_inline_formulae(tex):
    pattern = r'\$(.*?)\$'
    m = re.search(pattern, tex, re.M|re.S)
    while m:
        inner = process_math_hashes(m.group(1))
        replacement = '\0' + inner + '\1'
        tex = tex.replace(m.group(0), replacement)
        m = re.search(pattern, tex, re.M|re.S)
    tex = re.sub('\0', r'\(', tex)
    return re.sub('\1', r'\)', tex)

def process_quotes(tex):
    return re.sub(r"``(.*?)''", r'<q>\1</q>', tex, 0, re.M|re.S)

def process_display_formulae2(tex, begin, end):
    pattern = re.escape(begin) + r'(.*?)' + re.escape(end)
    m = re.search(pattern, tex, re.M|re.S)
    while m:
        inner = process_math_hashes(m.group(1))
        replacement = '\0' + inner + '\1'
        tex = tex[:m.start()] + replacement + tex[m.end():]
        m = re.search(pattern, tex, re.M|re.S)
    tex = tex.replace('\0', begin)
    tex =  tex.replace('\1', end)
    return tex

def process_display_formulae(tex):
    tex = process_display_formulae2(tex, r'\[', r'\]')
    tex = process_display_formulae2(tex, r'\begin{equation}', r'\end{equation}')
    tex = process_display_formulae2(tex, r'\begin{align*}', r'\end{align*}')
    tex = process_display_formulae2(tex, r'\begin{eqnarray*}', r'\end{eqnarray*}')
    return tex

def strip_comments(tex):
    lines = tex.splitlines()
    nulled = set()
    for i in range(len(lines)):
        if len(lines[i]) > 0:
            lines[i] = re.sub(r'(^|[^\\])\%.*$', r'\1', lines[i])
            if len(lines[i]) == 0:
                nulled.add(i)
    lines = [lines[i] for i in range(len(lines)) if i not in nulled]
    return "\n".join(lines)

def process_tabulars(tex):
    pattern = r'\\begin{tabular}{.*?}(.*?)\\end{tabular}'
    m = re.search(pattern, tex, re.M|re.S)
    while m:
        i = m.start()
        j = m.end()
        rows = re.split(r'\\\\', m.group(1))
        rows = [re.split(r'\&', r) for r in rows]
        table = '<table align="center">'
        for r in rows:
            table += '<tr>'
            for c in r:
                table += '<td>' + c + '</td>'
            table += '</tr>'
        table += '</table>'
        tex = tex[:i] + table + tex[j:]
        m = re.match(pattern, tex, re.MULTILINE | re.DOTALL)
    return tex

def process_figures(tex):
    pattern = r'\\begin{figure}(.*?)\\end{figure}'
    replacement = r'<div class="figure">\1</div>'
    return re.sub(pattern, replacement, tex, 0, re.MULTILINE | re.DOTALL)

def process_command(tex, cmd, htmlhead, htmltail):
    pattern = '\\' + cmd
    i = tex.find(pattern)
    while i >= 0:
        j = i+len(pattern)
        j, k = get_arg(tex, j)
        arg = tex[j:k]
        replacement = htmlhead + arg + htmltail
        tex = tex[:i] + replacement + tex[k+1:]
        i = tex.find(pattern)
    return tex

def process_captions(tex):
    cmd = 'caption'
    htmlhead = '<div class="caption">'
    htmltail = '</div>'
    return process_command(tex, cmd, htmlhead, htmltail)

def process_emphasis(tex):
    cmd = 'emph'
    htmlhead = '<em>'
    htmltail = '</em>'
    return process_command(tex, cmd, htmlhead, htmltail)

def process_paragraphs(tex):
    cmd = 'paragraph'
    htmlhead = '<span class="paragraph">'
    htmltail = '</span>'
    return process_command(tex, cmd, htmlhead, htmltail)

def process_refs_and_labels(tex):
    headings = ['chapter'] + ['sub'*i + 'section' for i in range(4)]
    reh = r'(' + '|'.join(headings) + r'){(.+?)}'
    environments = ['thm', 'lem', 'exc', 'figure', 'equation']
    ree = r'begin{(' + '|'.join(environments) + r')}'
    rel = r'(\w+)label{(.+?)}'
    bigone = r'\\({})|\\({})|\\({})'.format(reh, ree, rel)

    sec_ctr = [0]*(len(headings)+1)
    env_ctr = [0]*len(environments)
    html = []
    splitters = [0]
    lastlabel = None
    labelmap = dict()
    for m in re.finditer(bigone, tex):
        #print(m.groups())
        if m.group(2):
            splitters.append(m.start())
            # This is a sectioning command
            i = headings.index(m.group(2))
            if i == 0:
                env_ctr = [0]*len(env_ctr)
            sec_ctr[i:] = [sec_ctr[i]+1]+[0]*(len(headings)-i-1)
            for j in range(i+1, len(sec_ctr)): sec_ctr[j] = 0
            # print(sec_ctr[:i+1], m.group(3))
            idd = m.group(2) + ":" + ".".join([str(x) for x in sec_ctr[:i+1]])
            lastlabel = idd
            html.append("<a id='{}'></a>".format(idd))
            #print(html[-1])
        elif m.group(5):
            splitters.append(m.start())
            # This is an environment
            i = environments.index(m.group(5))
            env_ctr[i] += 1
            idd = "{}:{}.{}".format(m.group(5), sec_ctr[0], env_ctr[i])
            lastlabel = idd
            html.append("<a id='{}'></a>".format(idd))
            #print(html[-1])
        elif m.group(7):
            # This is a labelling command
            label = "{}:{}".format(m.group(7), m.group(8))
            labelmap[label] = lastlabel
            print("{}=>{}".format(label, labelmap[label]))
    splitters.append(len(tex))
    chunks = [tex[splitters[i]:splitters[i+1]] for i in range(len(splitters)-1)]
    zipped = [chunks[i] + html[i] for i in range(len(html))]
    zipped.append(chunks[-1])
    tex = "".join(zipped)
    tex = re.sub(r'^\s*\\(\w+)label{[^}]+}\s*?$\n', '', tex, 0, re.M|re.S)
    tex = re.sub(r'\\(\w+)label{(.+?)}', '', tex)
    return tex, labelmap

def process_references(tex, labelmap):
    map = dict([('chap', 'Chapter'),
                ('sec', 'Section'),
                ('thm', 'Theorem'),
                ('lem', 'Lemma'),
                ('fig', 'Figure'),
                ('eq', 'Equation'),
                ('exc', 'Exercise')])
    pattern = r'\\(\w+)ref{(.*?)}'
    m = re.search(pattern, tex)
    while m:
        label = "{}:{}".format(m.group(1), m.group(2))
        if label not in labelmap:
            print("Info: undefined label {}".format(label))
            idd = 'REFERR'
            num = '??'
        else:
            idd = labelmap[label]
            num = idd[idd.find(':')+1:]
        html = '<a href="#{}">{}&nbsp;{}</a>'.format(idd, map[m.group(1)], num)
        print(html)
        tex = tex[:m.start()]  + html + tex[m.end():]
        m = re.search(pattern, tex)
    return tex

def process_headings(tex):
    chapter = "None"  # FIXME
    cmd = 'chapter'
    m = re.search(r'\\chapter{(.*?)}', tex)
    if m: chapter = m.group(1) # FIXME: Cleanup and markup here
    htmlhead = '<div class="chapter">'
    htmltail = '</div>'
    tex = process_command(tex, cmd, htmlhead, htmltail)
    for i in range(4):
        cmd = ('sub'*i) + 'section'
        htmlhead = '<h{}>'.format(i+1)
        htmltail = '</h{}>'.format(i+1)
        tex = process_command(tex, cmd, htmlhead, htmltail)
    return chapter, tex

def process_centers(tex):
    pattern = r'\\begin{center}(.*?)\\end{center}'
    replacement = r'<div class="center">\1</div>'
    return re.sub(pattern, replacement, tex, 0, re.M|re.S)

def process_proofs(tex):
    pattern = r'\\begin{proof}(.*?)\\end{proof}'
    replacement = r'<div class="proof">\1</div>'
    return re.sub(pattern, replacement, tex, 0, re.M|re.S)

def process_theorem_like(tex, env, name):
    pattern = r'\\begin{{{}}}(.*?)\\end{{{}}}'.format(env, env)
    replacement = r'<div class="{}">\1</div>'.format(env)
    return re.sub(pattern, replacement, tex, 0, re.M|re.S)

def process_oneline_dontcares(tex):
    commands = ['noindent', 'hline', 'vspace', 'hspace', 'index', 'hspace',
                'setlength', 'newlength', 'addtolength', 'qedhere',
                'pagenumbering']
    dontcare = "(" + "|".join(commands) + ")"
    # pattern2 deals with the case where this creates a blank line
    pattern = r'\\' + dontcare + r'({.+?})*'
    pattern2 = r'^\s*\\' + dontcare + r'({[^}]+})*\s*?$\n'
    return re.sub(pattern2, '', tex, 0, re.M|re.S)
    return re.sub(pattern, '', tex, 0, re.M|re.S)

def process_lists(tex):
    # FIXME: Eliminate paragraph breaks between list items
    tex = re.sub(r'\\begin{itemize}', '<ul>', tex)
    tex = re.sub(r'\\end{itemize}', '\1</ul>', tex)
    tex = re.sub(r'\\begin{enumerate}', '<ol>', tex)
    tex = re.sub(r'\\end{enumerate}', '\1</ol>', tex)
    tex = re.sub(r'\\item', '\0', tex)
    tex = re.sub('\0([^\0\1]*)', r'<li>\1</li>', tex, 0, re.M|re.S)
    return tex
"""
def process_labels(tex):
    pattern = r'\\(\w+)label{(.*?)}'
    m = re.search(pattern, tex)
    while m:
        label = "{}:{}".format(m.group(1), m.group(2))
        if label in g_labels:
            print("Info: multiply-defined label".format(label))
        g_labels.add(label)
        tag = '<a name="{}"></a>'.format(label)
        tex = tex[:m.start()]  + tag + tex[m.end():]
        m = re.search(pattern, tex)
    return tex

def process_references(tex, labelmap):
    map = dict([('chap', 'Chapter'),
                ('sec', 'Section'),
                ('thm', 'Theorem'),
                ('lem', 'Lemma'),
                ('fig', 'Figure'),
                ('myeq', 'Equation'),
                ('exc', 'Exercise'),
                ('page', 'Page')])
    pattern = r'\\(\w+)ref{(.*?)}'

    m = re.search(pattern, tex)
    while m:
        label = "{}:{}".format(m.group(1), m.group(2))
        if label not in g_labels:
            print("Info: unknown label {}".format(label))
        tag = '<a href="#{}">this {}</a>'.format(label, map[m.group(1)])
        tex = tex[:m.start()]  + tag + tex[m.end():]
        m = re.search(pattern, tex)
    return tex
"""
def process_imports(tex):
    pattern = r'\\(cpp|java|code|pcode)import{([^}]+)}'
    replacement = r'<div class="import">\\\1import{\2}</div>'
    return re.sub(pattern, replacement, tex)

def process_onlies(tex):
    languages = ['cpp', 'java', 'pcode']
    for lang in languages:
        tex = process_command(tex, lang+'only', "<!--", "-->")
    return tex

def process_graphics(tex):
    pattern = r'\\includegraphics(\[.*?\]){(.*?)}'
    replacement = r'<img scale="120%" src="\2.svg"/>'
    return re.sub(pattern, replacement, tex)

def process_citations(tex):
    return process_command(tex, 'cite', "[", "]")

def process_etals(tex):
    pattern = r'\\etal\\?'
    replacement = '<em>et al</em>'
    return re.sub(pattern, replacement, tex)

def tex2html(tex):
    # The ordering here is important
    tex = r'$\newcommand{\E}{\mathrm{E}}$' + tex
    tex = re.sub(r'\\myeqref', r'\eqref', tex)
    tex = preprocess_hashes(tex)
    tex = strip_comments(tex)
    tex = process_oneline_dontcares(tex)
    tex = process_onlies(tex)  # danger --- this needs to be better
    tex = process_inline_formulae(tex)
    tex = process_display_formulae(tex)
    tex = process_nonmath_hashes(tex)
    tex = process_quotes(tex)

    tex, labelmap = process_refs_and_labels(tex)
    tex = process_references(tex, labelmap)
    chapter, tex = process_headings(tex)

    tex = process_tabulars(tex)
    tex = process_figures(tex)
    tex = process_captions(tex)
    tex = process_centers(tex)
    tex = process_theorem_like(tex, 'thm', 'Theorem')
    tex = process_theorem_like(tex, 'lem', 'Lemma')
    tex = process_theorem_like(tex, 'exc', 'Exercise')
    tex = process_proofs(tex)

    tex = process_emphasis(tex)
    tex = process_paragraphs(tex)
    tex = process_citations(tex)
    tex = process_etals(tex)

    tex = process_lists(tex)
    tex = process_imports(tex)

    tex = process_graphics(tex)
    #tex = process_labels(tex)
    #tex = process_references(tex)
    tex = split_paragraphs(tex)
    return chapter, tex


inputs = [ 'intro', 'arrays', 'linkedlists', 'skiplists', 'hashing',
	   'binarytrees', 'rbs', 'scapegoat', 'redblack', 'heaps', 'sorting',
           'graphs', 'integers', 'btree']

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.err.write("Usage: {} <ipefile>\n".format(sys.argv[0]))
        sys.exit(-1)
    filename = sys.argv[1]
    base, ext = os.path.splitext(filename)
    outfile = base + ".html"
    print("Reading from {} and writing to {}".format(filename, outfile))

    # Read and translate the input
    tex = open(filename).read()
    chapter, htm = tex2html(tex)

    # Write the output
    (head, tail) = re.split('CONTENT', open('head.htm').read())
    head = re.sub('TITLE', chapter, head)
    of = open(outfile, 'w')
    of.write(head)
    of.write(htm)
    of.write(tail)
    of.close()
