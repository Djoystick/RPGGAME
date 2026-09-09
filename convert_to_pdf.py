import os
import markdown
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QTextDocument, QPdfWriter, QPageLayout, QPageSize
from PySide6.QtCore import QMarginsF

def md_to_pdf(input_md: str, output_pdf: str):
    with open(input_md, "r", encoding="utf-8") as f:
        md_text = f.read()

    html_content = markdown.markdown(
        md_text,
        extensions=["extra", "tables", "fenced_code", "nl2br"]
    )

    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.5;
            color: #1a1a1a;
            margin: 15px;
        }}
        h1 {{
            font-size: 18pt;
            color: #8b1818;
            border-bottom: 2px solid #8b1818;
            padding-bottom: 5px;
            margin-top: 15px;
        }}
        h2 {{
            font-size: 14pt;
            color: #23212b;
            border-bottom: 1px solid #c8963e;
            padding-bottom: 4px;
            margin-top: 16px;
        }}
        h3 {{
            font-size: 11pt;
            color: #631414;
            margin-top: 10px;
        }}
        blockquote {{
            background-color: #f7f4ec;
            border-left: 4px solid #c8963e;
            padding: 8px 12px;
            margin: 10px 0;
            font-style: italic;
        }}
        code {{
            background-color: #f0edf5;
            color: #5b21b6;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: Consolas, monospace;
            font-size: 9.5pt;
        }}
        pre {{
            background-color: #1e1e24;
            color: #f8f8f2;
            padding: 8px;
            border-radius: 4px;
            font-family: Consolas, monospace;
            font-size: 9pt;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 12px 0;
        }}
        th, td {{
            border: 1px solid #ccc;
            padding: 5px 8px;
            text-align: left;
        }}
        th {{
            background-color: #ede8d0;
            color: #333;
        }}
        ul, ol {{
            margin: 6px 0;
            padding-left: 20px;
        }}
        li {{
            margin-bottom: 3px;
        }}
        hr {{
            border: 0;
            height: 1px;
            background: #c8963e;
            margin: 15px 0;
        }}
    </style>
    </head>
    <body>
    {html_content}
    </body>
    </html>
    """

    app = QApplication.instance() or QApplication([])
    doc = QTextDocument()
    doc.setHtml(styled_html)

    writer = QPdfWriter(output_pdf)
    layout = QPageLayout(
        QPageSize(QPageSize.A4),
        QPageLayout.Portrait,
        QMarginsF(12, 12, 12, 12)
    )
    writer.setPageLayout(layout)
    doc.print_(writer)
    print(f"PDF successfully created at: {output_pdf}")

if __name__ == "__main__":
    md_to_pdf("astra_master_prompt.md", "MASTER_GAME_DESIGN_DOCUMENT.pdf")
