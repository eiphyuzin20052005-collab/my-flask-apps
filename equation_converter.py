import re


def format_math(s):
    if not s:
        return ''

    pattern = r'([a-zA-Z0-9\(\)\+\-\*\=\/]*\^[0-9a-zA-Z]+[a-zA-Z0-9\(\)\+\-\*\=\/]*)'

    def replace_math(match):
        val = match.group(0)
        return f'${val}$'

    return re.sub(pattern, replace_math, str(s))


# ==========================
# Text
# ==========================

def format_question(text):

    if text is None:
        return ""

    return str(text)


# ==========================
# Math convert
# ==========================

def math_convert(text):

    text = str(text)
    # keep matrix multiplication format
    text = re.sub(
        r'([A-Za-z]\^\d+)\s*=\s*(\[\[.*?\]\])',
        r'\1=\2',
        text
    )
    # symbols
    text = text.replace("×", r"\times")
    text = text.replace("÷", r"\div")


    # square root
    text = re.sub(
        r'√([A-Za-z0-9]+)',
        r'\\sqrt{\1}',
        text
    )


    # power number
    text = re.sub(
        r'([A-Za-z0-9]+)\^(\d+)',
        r'\1^{\2}',
        text
    )


    # Matrix inverse A^-1
    text = re.sub(
        r'([A-Za-z])\^-1',
        r'\1^{-1}',
        text
    )


    # Matrix transpose A^T
    text = re.sub(
        r'([A-Za-z])\^T',
        r'\1^{T}',
        text
    )


    # subscript A_1
    text = re.sub(
        r'([A-Za-z])_(\d+)',
        r'\1_{\2}',
        text
    )


    # determinant
    text = text.replace(
        "det(",
        r"\det("
    )


    # lambda
    text = text.replace(
        "lambda",
        r"\lambda"
    )


    # fraction
    text = re.sub(
        r'(\d+)\s*/\s*(\d+)',
        r'\\frac{\1}{\2}',
        text
    )


    # matrix [[1,2],[3,4]]
    def matrix_replace(match):

        content = match.group(1)

        rows = re.split(r'\]\s*,\s*\[', content)

        latex_rows = []

        for row in rows:
            row = row.replace("[", "").replace("]", "")
            cols = [c.strip() for c in row.split(",")]
            latex_rows.append(" & ".join(cols))

        return (
            r"\begin{bmatrix}"
            + r" \\ ".join(latex_rows)
            + r"\end{bmatrix}"
        )


    text = re.sub(
        r'\[\[(.*?)\]\]',
        matrix_replace,
        text,
        flags=re.DOTALL
    )


    return text



# ==========================
# Find math part
# ==========================

def convert_line(line):

    if line is None:
        return ""

    line = line.strip()

    if line == "":
        return ""


    # Matrix
    matrix_pattern = r'(\[\[.*?\]\])'


    # Equation / expression pattern
    math_pattern = (
        r'('
        r'[A-Za-z0-9]+'
        r'(?:\^?\d*)?'
        r'(?:\s*[+\-×÷*/=]\s*'
        r'[A-Za-z0-9\^]+)+'
        r'|'
        r'[A-Za-z]\^\d+'
        r'|'
        r'√[A-Za-z0-9]+'
        r'|'
        r'\b(?:sin|cos|tan)\s*\d+'
        r'|'
        r'\d+/\d+'
        r'|'
        r'[A-Za-z]\^-1'
        r'|'
        r'[A-Za-z]\^T'
        r'|'
        r'det\([A-Za-z]\)'
        r')'
    )


    pattern = (
        matrix_pattern
        + "|"
        + math_pattern
    )


    matches = re.finditer(
        pattern,
        line,
        re.DOTALL
    )


    result = ""

    last = 0


    for m in matches:

        start, end = m.span()

        result += line[last:start]


        math_part = m.group()


        if math_part.isalpha():

            result += math_part

        else:

            result += (
                "$"
                + math_convert(math_part)
                + "$"
            )


        last = end


    result += line[last:]


    return result



# ==========================
# Main
# ==========================

def convert_equation(text):

    if text is None:
        return ""


    text = format_question(text)


    lines = text.split("\n")
    

    output = []


    for line in lines:

        output.append(
            convert_line(line)
        )


    return "<br>".join(output)