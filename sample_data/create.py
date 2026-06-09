from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors

data = [
    ['Date', 'Description', 'Amount'],
    ['2026-04-05', 'T1908 GRAB CITY', '-50000'],
    ['2026-04-10', 'MACBOOK PRO 14 SHOPEE', '-35000000'],
    ['2026-04-12', 'FT0024112501 ID:0001', '-250000'],
    ['2026-04-15', 'VINMART HCM 04', '-120000'],
    ['2026-04-20', 'NETFLIX SUBSCRIPTION', '-250000'],
    ['2026-04-30', 'SALARY MAY', '20000000']
]

pdf = SimpleDocTemplate('/app/bank_statement_sample.pdf', pagesize=letter)
table = Table(data)

style = TableStyle([
    ('BACKGROUND', (0,0), (-1,0), colors.grey),
    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('BOTTOMPADDING', (0,0), (-1,0), 12),
    ('BACKGROUND', (0,1), (-1,-1), colors.beige),
    ('GRID', (0,0), (-1,-1), 1, colors.black)
])
table.setStyle(style)
pdf.build([table])
