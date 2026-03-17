import csv
import sys
from datetime import datetime


def convert_csv(input_file):
    output_fieldnames = ['Date', 'Payee', 'Memo', 'Outflow', 'Inflow']

    writer = csv.DictWriter(sys.stdout, fieldnames=output_fieldnames)
    writer.writeheader()

    with open(input_file, 'r', encoding='utf-16') as f:
        reader = csv.DictReader(f, delimiter='\t')

        for row in reader:
            date = row['Kirjauspäivä']

            amount = float(row['Summa'].replace(',', '.'))
            outflow = abs(amount) if amount < 0 else ''
            inflow = amount if amount > 0 else ''

            memo = row['Tapahtumateksti'].strip()
            if not memo:
                memo = row['Tapahtumatyyppi']

            output_row = {
                'Date': date,
                'Payee': row['Arvopaperi'],
                'Memo': memo,
                'Outflow': outflow,
                'Inflow': inflow,
            }

            writer.writerow(output_row)


def main():
    if len(sys.argv) != 2:
        print("Usage: python nordnet.py input_file.csv", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    try:
        convert_csv(input_file)
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
