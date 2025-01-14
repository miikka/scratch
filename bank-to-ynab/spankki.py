import csv
import sys
from datetime import datetime

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
            # Skip specified transactions
            if (row['Tapahtumalaji'] == 'TILISIIRTO' and
                row['Maksaja'] == 'KOSKINEN MIIKKA ILMARI'):
                continue

            # Convert date format (assuming input is DD.MM.YYYY)
            date_str = row['Kirjauspäivä']
            date_obj = datetime.strptime(date_str, '%d.%m.%Y')
            formatted_date = date_obj.strftime('%Y-%m-%d')

            # Determine if amount is outflow or inflow
            amount = float(row['Summa'].replace(',', '.'))
            outflow = abs(amount) if amount < 0 else ''
            inflow = amount if amount > 0 else ''

            memo = row['Viesti'].strip("'")
            if not memo or memo == "-":
                memo = row['Tapahtumalaji']

            # Create output row
            output_row = {
                'Date': formatted_date,
                'Payee': row['Saajan nimi'] if amount < 0 else row['Maksaja'],
                'Memo': memo,
                'Outflow': outflow,
                'Inflow': inflow
            }

            writer.writerow(output_row)

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py input_file.csv", file=sys.stderr)
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
