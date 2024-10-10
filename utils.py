import csv

def get_dict_name_serial(file_path):
    name_serial_dict = {}
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file, delimiter=';')
        header = next(reader)  # Skip the header
        name_idx, serial_idx = header.index('Name'), header.index('SerialNumber')
        
        for row in reader:
            if len(row) > serial_idx and row[name_idx] and row[serial_idx]:
                name_serial_dict[row[name_idx]] = row[serial_idx]
    
    return name_serial_dict
