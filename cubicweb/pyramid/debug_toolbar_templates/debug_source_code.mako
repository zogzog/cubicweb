<html>
<head>
    <title>${file_path}</title>
</head>
<body>
    <h2>${file_path}</h2>

    % if has_pygments:
    ${highlight_html(content, "python", linenos=True, hl_lines=lines, lineanchors="line")}
    % else:
    <table class="rawtable">
    % for line_number, source_line in enumerate(content.split("\n"), start=1):
        <tr>
        <td class="line_number">
            <pre>${line_number}</pre>
        </td>
        <td>
            % if line_number in lines:
            <a class="highlight-line" name="line-${line_number}">
            % else:
            <a name="line-${line_number}">
            % endif
                <pre>${source_line.rstrip()} </pre>
            </a>
        </td>
        </tr>
    % endfor
    </table>
    % endif

    <style>
    h2 {
        text-align: center;
        width: 100%%;
        color: #fefefe;
        background-color: #333333;
        padding: 10px;
        font-family: sans;
        margin: 0;
    }

    body {
        margin: 0;
    }

    .highlighttable, .rawtable {
        margin: auto;
        font-size: larger;
        border: 2px solid black;
        border-top: 0;
        border-bottom: 0;
    }

    .rawtable {
        padding: 10px;
    }

    pre {
        margin: 0;
    }

    .line_number {
        text-align: right;
    }

    .rawtable td {
        padding: 0;
    }

    .hll {
        display: block;
    }

    .highlight-line > pre {
        background-color: #ffffcc;
    }

    ${css}

    </style>
</body>
</html>
