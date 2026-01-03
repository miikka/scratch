import csv
import sys
from datetime import datetime

SKIP_INTERNAL = False


def convert_csv(input_file):
    # Define the output fieldnames
    output_fieldnames = ['Date', 'Payee', 'Memo', 'Outflow', 'Inflow']

    # Create CSV writer for stdout
    writer = csv.DictWriter(sys.stdout, fieldnames=output_fieldnames)
    writer.writeheader()

    # Read the input CSV file
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')

        for row in reader:
            # Skip internal transfers if configured
            if (SKIP_INTERNAL and row['Selitys'] == 'TILISIIRTO'):
                continue

            # Date is already in YYYY-MM-DD format
            formatted_date = row['Kirjauspäivä']

            # Determine if amount is outflow or inflow
            amount = float(row['Määrä EUROA'].replace(',', '.'))
            outflow = abs(amount) if amount < 0 else ''
            inflow = amount if amount > 0 else ''

            # Use message for memo, fallback to description
            memo = row['Viesti'].strip()
            if not memo or memo == "-":
                memo = row['Selitys']

            # Create output row
            output_row = {
                'Date': formatted_date,
                'Payee': row['Saaja/Maksaja'],
                'Memo': memo,
                'Outflow': outflow,
                'Inflow': inflow
            }

            writer.writerow(output_row)

def main():
    if len(sys.argv) != 2:
        print("Usage: python op.py input_file.csv", file=sys.stderr)
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
