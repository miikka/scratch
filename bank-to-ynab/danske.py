import csv
import datetime

def convert_csv(input_file, outfile):
    # Open input file with ISO-8859-1 encoding
    with open(input_file, 'r', encoding='iso-8859-1') as infile:
        # Create CSV readers and writers
        reader = csv.DictReader(infile, delimiter=';')
        writer = csv.DictWriter(outfile, fieldnames=['Date', 'Payee', 'Memo', 'Outflow', 'Inflow'])

        # Write header
        writer.writeheader()

        # Process each row
        for row in reader:
            payee = row['Saaja/Maksaja']
            if payee == "Varaus":
                continue

            # Convert date format if needed
            try:
                date = datetime.datetime.strptime(row['Pvm'], '%d.%m.%Y').strftime('%Y-%m-%d')
            except ValueError:
                date = row['Pvm']

            # Convert amount to positive/negative values
            amount = row['Määrä'].replace(',', '.').strip()
            try:
                amount_float = float(amount)
                outflow = abs(amount_float) if amount_float < 0 else ''
                inflow = amount_float if amount_float > 0 else ''
            except ValueError:
                outflow = ''
                inflow = ''

            # Create memo from Luokka and Alaluokka
            memo = f"{row['Luokka'].strip()} - {row['Alaluokka'].strip()}" if row['Alaluokka'] else row['Luokka']

            # Write new row
            writer.writerow({
                'Date': date,
                'Payee': payee,
                'Memo': memo,
                'Outflow': outflow,
                'Inflow': inflow
            })

# Usage
import sys

if len(sys.argv) != 2:
    print("Usage: script.py input_file")
    sys.exit(1)

input_file = sys.argv[1]
convert_csv(input_file, sys.stdout)
