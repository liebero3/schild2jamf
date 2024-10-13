# schild2jamf.py

import argparse
import xml.etree.ElementTree as ET

# import re
# import utils
import os
import csv
from unidecode import unidecode


class User:
    def __init__(
        self,
        lehrerid,
        name,
        given,
        institutionrole,
        email,
        birthday,
        username,
        initialpassword,
    ):
        self.lehrerid = lehrerid
        self.name = name
        self.given = given
        self.institutionrole = institutionrole
        self.email = email
        self.birthday = birthday
        self.username = username
        self.initialpassword = initialpassword

    def __repr__(self):  # optional
        return f"User {self.name}"


class Group:
    def __init__(self, groupid, name, parent):
        self.groupid = groupid
        self.name = name
        self.parent = parent

    def __repr__(self):  # optional
        return f"Group {self.name}"


class Membership:
    def __init__(self, membershipid, groupid, nameid):
        self.membershipid = membershipid
        self.groupid = groupid
        self.nameid = nameid

    def __repr__(self):  # optional
        return f"Membership {self.groupid}"


def parse_users(users, root):

    for elem in root.findall(
        ".//{http://www.metaventis.com/ns/cockpit/sync/1.0}person"
    ):
        # Extracts the ID for each person
        for child in elem.findall(
            ".//{http://www.metaventis.com/ns/cockpit/sync/1.0}id"
        ):
            lehrerid = child.text

        # Extracts the last name
        for child in elem.findall(
            ".//{http://www.metaventis.com/ns/cockpit/sync/1.0}family"
        ):
            name = child.text

        # Extracts the given name
        for child in elem.findall(
            ".//{http://www.metaventis.com/ns/cockpit/sync/1.0}given"
        ):
            given = child.text

        # Extracts the user's role within the institution
        for child in elem.findall(
            ".//{http://www.metaventis.com/ns/cockpit/sync/1.0}institutionrole"
        ):
            institutionrole = child.get("institutionroletype")

        # Attempts to find and store the email, defaults to an empty string
        email = ""
        for child in elem.findall(
            ".//{http://www.metaventis.com/ns/cockpit/sync/1.0}email"
        ):
            email = child.text

        # Handles student-specific attributes
        if institutionrole == "Student":
            for child in elem.findall(
                ".//{http://www.metaventis.com/ns/cockpit/sync/1.0}bday"
            ):
                birthdaytemp = child.text.split("-")
                birthday = f"{birthdaytemp[2]}.{birthdaytemp[1]}.{birthdaytemp[0]}"
            # Generates a username for students in shortform
            tempusername = return_username(given, name, "kurzform")

        # Handles faculty or extern-specific attributes
        if institutionrole == "faculty" or institutionrole == "extern":
            # Generates a username in "vorname.nachname" format
            tempusername = return_username(given, name, "vorname.nachname")
            birthday = ""

        # Resolves duplicate usernames by appending '1' if necessary
        for user in users:
            if tempusername == user.username:
                tempusername = tempusername + "1"

        # Calculates the initial password
        initialPassword = f"{lehrerid[-3:]}{tempusername[-2:]}{strip_hyphens_from_birthday(birthday)[:3]}{tempusername[:2]}"

        # Appends a new User object to the users list with all extracted and calculated data
        users.append(
            User(
                lehrerid,
                name,
                given,
                institutionrole,
                email,
                birthday,
                tempusername,
                initialPassword,
            )
        )


def parse_groups(groups, root):

    parent = ""  # Initialize the parent variable for storing parent group ID

    # Find all 'group' elements in the XML document using the specific namespace
    for elem in root.findall(".//{http://www.metaventis.com/ns/cockpit/sync/1.0}group"):

        # Extract the group ID from each group element
        for child in elem.findall(
            "{http://www.metaventis.com/ns/cockpit/sync/1.0}sourcedid/{http://www.metaventis.com/ns/cockpit/sync/1.0}id"
        ):
            groupid = child.text  # Get the text of the current XML element

        # Extract the short description of the group, which serves as the group's name
        for child in elem.findall(
            "{http://www.metaventis.com/ns/cockpit/sync/1.0}description/{http://www.metaventis.com/ns/cockpit/sync/1.0}short"
        ):
            name = child.text  # Get the text of the current XML element

        # Extract the parent ID of the current group, if it exists
        for child in elem.findall(
            "{http://www.metaventis.com/ns/cockpit/sync/1.0}relationship/{http://www.metaventis.com/ns/cockpit/sync/1.0}sourcedid/{http://www.metaventis.com/ns/cockpit/sync/1.0}id"
        ):
            parent = child.text  # Get the text of the current XML element

        # Create a Group object and append it to the groups list
        groups.append(Group(groupid, name, parent))


def parse_memberships(memberships, root):

    i = 0  # Initialize a counter for membership IDs
    # Find all membership elements in the XML document using the specific namespace
    for elem in root.findall(
        ".//{http://www.metaventis.com/ns/cockpit/sync/1.0}membership"
    ):
        # Extract the group ID from the membership element
        for child in elem.findall(
            "{http://www.metaventis.com/ns/cockpit/sync/1.0}sourcedid/{http://www.metaventis.com/ns/cockpit/sync/1.0}id"
        ):
            groupid = (
                child.text
            )  # Get the text of the current XML element representing the group ID
        # Extract the member ID associated with the group
        for child in elem.findall(
            "{http://www.metaventis.com/ns/cockpit/sync/1.0}member/{http://www.metaventis.com/ns/cockpit/sync/1.0}sourcedid/{http://www.metaventis.com/ns/cockpit/sync/1.0}id"
        ):
            nameid = (
                child.text
            )  # Get the text of the current XML element representing the member ID
        # Create a Membership object and append it to the memberships list
        memberships.append(Membership(i, groupid, nameid))
        i += 1  # Increment the membership ID counter


def parse_xml(users, groups, memberships, root):

    # Parse user data from the XML and populate the users list with User objects
    parse_users(users, root)

    # Parse group data from the XML and populate the groups list with Group objects
    parse_groups(groups, root)

    # Parse membership data from the XML and populate the memberships list with Membership objects
    parse_memberships(memberships, root)


def parse_year(xmlfile):

    # Iterate over possible year representations from '00' to '99'
    for i in range(10):
        for j in range(10):
            # Open the XML file for reading
            with open(xmlfile) as f:
                # Construct the school year format '20ij/ij+1' and check if it exists in the file
                if f"20{i}{j}/{i}{j+1}" in f.read():
                    # If found, print the year
                    print(f"{i}{j}/{i}{j+1}")
                    # Return the year as a two-digit string representing the starting year
                    return f"{i}{j}"

                # Construct the school year format '20ij/i+10' and check if it exists in the file
                if f"20{i}{j}/{i+1}0" in f.read():
                    # If found, print the year
                    print(f"{i}{j}/{i+1}0")
                    # Return the year as a two-digit string representing the starting year
                    return f"{i}{j}"


def return_webuntis_uid(user):

    return (
        return_username(
            user.given, user.name, "kurzform"
        )  # Generate a short form username if 'X' is in the LehrerID
        if "X" in user.lehrerid  # Check if 'X' is present in the LehrerID
        else user.lehrerid[
            10:
        ]  # Otherwise, slice the LehrerID starting from the 11th character
    )


def custom_transliterate(name):
    translations = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"}
    for original, replacement in translations.items():
        name = name.replace(original, replacement)
    return unidecode(name)


def return_username(given, last, typ):

    if typ == "vorname.nachname":
        # For the "vorname.nachname" format:
        # - Translate the given name using the mapping and split it on spaces,
        #   taking only the first segment.
        # - Concatenate with a period and the translated last name,
        #   removing any spaces or hyphens.
        username = (
            custom_transliterate(given).split(" ")[0]
            + "."
            + custom_transliterate(last).replace(" ", "").replace("-", "")
        )
    if typ == "kurzform":
        # For the "kurzform" type:
        # - Translate the given name using the mapping and take the first 4 characters.
        # - Translate the last name using the mapping,
        #   removing spaces and hyphens, then take the first 4 characters.
        username = (
            custom_transliterate(given).split(" ")[0][:4]
            + custom_transliterate(last).replace(" ", "").replace("-", "")[:4]
        )

    # Return the generated username in lowercase.
    return username.lower()


def strip_hyphens_from_birthday(birthday: str):

    return birthday.replace("-", "")


def return_initial_password(user):

    # Construct the initial password using parts of the user's attributes:

    # Take the last 3 characters from the user's teacher ID (lehrerid)
    part_lehrerid = user.lehrerid[-3:]

    # Take the last 2 characters from the user's username
    part_username_suffix = user.username[-2:]

    # Remove hyphens from the user's birthday, then take the first 3 characters
    part_birthday = strip_hyphens_from_birthday(user.birthday)[:3]

    # Take the first 2 characters from the user's username
    part_username_prefix = user.username[:2]

    # Return the assembled initial password as a concatenation of the above parts
    return f"{part_lehrerid}{part_username_suffix}{part_birthday}{part_username_prefix}"


def return_list_of_courses_of_student(studentid, memberships, groups):

    # Initialize an empty list to store course names for a given student
    courseslist = []

    # Get group IDs the student is a member of
    student_memberships = [
        membership.groupid
        for membership in memberships
        if membership.nameid == studentid
    ]

    # Map group IDs to group names using the provided groups list
    for group_id in student_memberships:
        group_matches = [group.name for group in groups if group.groupid == group_id]
        if group_matches:
            group_name = group_matches[0]
            if group_name:
                courseslist.append(group_name)

    return courseslist


def load_email_to_kuerzel(users_csv):

    mapping = {}
    with open(users_csv, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            email = row["email"].strip().lower()
            kuerzel = row["kuerzel"].strip()
            if email and kuerzel:
                mapping[email] = kuerzel
    return mapping


def load_mappinggroups(mappinggroups_csv):

    mappinggroups = {}
    with open(mappinggroups_csv, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            original = row["name"]
            mapped = row["newname"]
            mappinggroups[original] = mapped
    return mappinggroups


def get_classes(groups):
    classes = set()
    for group in groups:
        if group.name.startswith("Klasse "):
            classes.add(group.name.split(" ")[1])
    return sorted(list(classes))


def get_klasse_of_user(user, memberships, groups):
    # Holen Sie sich die Liste der Gruppen des Benutzers
    groups = return_list_of_courses_of_student(user.lehrerid, memberships, groups)
    # Gehe durch die Gruppen und suche nach der Klasse
    for group in groups:
        if group.startswith("Klasse ") and group.endswith("Schueler"):
            # Ermittelt den Teil nach 'Klasse '
            class_name = group.split(" ")[1]
            # Falls die Klasse in der erwarteten Liste enthalten ist, zurückgeben
            if class_name in [
                "05A",
                "05B",
                "05C",
                "05D",
                "06A",
                "06B",
                "06C",
                "06D",
                "06E",
                "07A",
                "07B",
                "07C",
                "07D",
                "08A",
                "08B",
                "08C",
                "09A",
                "09B",
                "09C",
                "10A",
                "10B",
                "10C",
                "EF",
                "Q2",
            ]:
                return class_name
    # Geben Sie None oder eine leere Zeichenkette zurück, wenn keine Klasse gefunden wurde
    return None


def shorten_group_name(name, groupid):
    if 'raum-kurs' in groupid:
        # Der letzte Teil wird aufgesplittet, um Handling von "- Lehrer" oder "- Schüler" zu erlauben
        name_parts = name.split(' - ')
        main_name_part = name_parts[0]
        
        # Hauptaufteilung des Namens, um auf den spezifischen Inhalt zuzugreifen
        main_name_parts = main_name_part.split(' (')
        
        if len(main_name_parts) < 2:
            return ""  # Wenn das Format des Namens nicht wie erwartet ist.
        
        first_split_parts = main_name_parts[0].split()
        first_part = first_split_parts[0]  # Fachkürzel

        second_part = ""
        if len(first_split_parts) > 1:
            second_part = first_split_parts[1]  # Kursmerkmal, falls vorhanden

        try:
            # Verarbeiten der in Klammern enthaltenen Teile
            inside_parens = main_name_parts[1].rstrip(')').split(', ')
            if len(inside_parens) < 4:
                return ""  # Fehlende Daten in Klammern
            
            year_gr = inside_parens[2]  # Jahrgangsstufe
            teacher = inside_parens[3]  # Kürzel des Lehrers/der Lehrenden

            suffix = ''
            if 'Lehrer' in name:
                suffix = 'L'
            elif 'Schueler' in name:
                suffix = 'S'

            shortname = f"{first_part}{second_part}{year_gr}{teacher}{suffix}"
            return shortname

        except IndexError:
            return ""

    elif 'raum-klasse' in groupid:
        if 'Betriebe' in name or 'Ausbilder' in name:
            return ""  # Überspringen
        
        class_parts = name.split()
        
        if len(class_parts) < 2:
            return ""

        class_name = class_parts[1]  # Beispiel: "07D"
        suffix = 'L' if 'Lehrer' in name else ('S' if 'Schueler' in name else '')
        shortname = f"{class_name}{suffix}"
        return shortname

    elif 'raum-fach' in groupid:
        return ""  # Return empty string

    return ""  # Falls kein gültiger `groupid`-Typ gefunden wird



def create_jamf_accounts(
    nameOfOutputCsv: str,
    dict_name_serial: dict,
    users,
    groups,
    memberships,
    mappinggroups: dict,
    klasse_filter: str = None,
):
    ser_nums = []  # List to hold serial numbers if required

    # Check if a specific CSV file exists for the provided class filter
    if klasse_filter and os.path.isfile(f"{klasse_filter}.csv"):
        with open(f"{klasse_filter}.csv", "r", encoding="utf-8") as file:
            reader = csv.reader(file)  # Create a CSV reader object
            next(reader)  # Skip the header line
            # Populate ser_nums with serial numbers from the specific file
            ser_nums = [dict_name_serial[rows[0]] for rows in reader]

    with open(nameOfOutputCsv, "w", encoding="utf-8") as f:
        # Define the headers for the output CSV file, including SerialNumber if needed
        if ser_nums:
            f.write("Username;Email;FirstName;LastName;Groups;Password;SerialNumber\n")
        else:
            f.write("Username;Email;FirstName;LastName;Groups;Password\n")

        i = 0  # Initialize counter for serial numbers
        for user in users:
            # Filter users by class if a class filter is applied
            if (
                klasse_filter
                and get_klasse_of_user(user, memberships, groups) != klasse_filter
            ):
                continue

            # Retrieve user courses and formats them into groups
            courses = return_list_of_courses_of_student(
                user.lehrerid, memberships, groups
            )

            # Check if the user is a student
            if "Alle - Schüler" in courses:
                # Filter and update groups
                filtered_groups = []
                for group in courses:
                    filtered_groups.append(group)

                updated_groups = []
                for group in filtered_groups:
                    mapped_group = mappinggroups.get(group, "")
                    if mapped_group != "":
                        updated_groups.append(mapped_group)

                groups_str = ""
                try:
                    groups_str = ",".join(updated_groups)
                except TypeError:
                    groups_str = ""

                # Add any additional student groups here if needed
                # groups_str += ",AdditionalStudentGroup1,AdditionalStudentGroup2"
            else:
                # If not a student, join the courses as before
                groups_str = ",".join(courses)

            # Map user info to the specific CSV structure
            user_data_mapping = {
                "Username": f"164501-{user.username}",
                "Email": f"{user.username}@164501.nrw.schule",
                "FirstName": f"{user.username[:4]}",
                "LastName": f"{user.username[4:]}",
                "Groups": groups_str,
                "Password": f"{return_initial_password(user)}",
            }

            # Write user data to the file, including serial numbers if available
            if ser_nums:
                f.write(
                    f"{user_data_mapping['Username']};{user_data_mapping['Email']};"
                    f"{user_data_mapping['FirstName']};{user_data_mapping['LastName']};"
                    f"{user_data_mapping['Groups']};{user_data_mapping['Password']};{ser_nums[i]}\n"
                )
                i += 1  # Increment the serial number index
            else:
                f.write(
                    f"{user_data_mapping['Username']};{user_data_mapping['Email']};"
                    f"{user_data_mapping['FirstName']};{user_data_mapping['LastName']};"
                    f"{user_data_mapping['Groups']};{user_data_mapping['Password']}\n"
                )


def create_jamf_accounts_teachers(
    nameOfOutputCsv: str,
    email_to_kuerzel: dict,
    users,
    groups,
    memberships,
    mappinggroups: dict,
    klasse_filter: str = None,
):
    classes = get_classes(groups)
    additional_groups = load_additional_groups_from_csv("teacher_additional_groups.csv")
    # print(additional_groups)
    with open(nameOfOutputCsv, "w", encoding="utf-8") as f:
        # Schreiben der Kopfzeile
        f.write("Username;Email;FirstName;LastName;TeacherGroups;Groups;Password\n")

        for user in users:
            # Überprüfe, ob der Benutzer ein Lehrer ist
            if user.institutionrole not in ("faculty", "extern"):
                continue
            # Abrufen der Kurse des Lehrers
            courses = return_list_of_courses_of_student(
                user.lehrerid, memberships, groups
            )
            # Prüfen, ob "AlleL" in den Gruppen ist
            if "Alle - Lehrer" in courses:
                # Filtern der Gruppen basierend auf bestimmten Kriterien
                filtered_groups = []
                # for group in groups_list.split(","):
                for group in courses:
                    # print(f"{user} ist in {group}")
                    filtered_groups.append(group)
                # Aktualisieren der Gruppennamen mit dem mappinggroups Dictionary
                updated_groups = []
                for group in filtered_groups:
                    mapped_group = mappinggroups.get(group, "")
                    if mapped_group != "" and mapped_group != "AlleL":
                        updated_groups.append(mapped_group)
                groups_str = ""
                try:
                    groups_str = ",".join(updated_groups)
                    # print(groups_str)
                    # TODO: hier teacher_additional_groups.csv einfügen
                    groups_str += "," + ",".join(additional_groups)
                    # groups_str += ",iPads-Lehrerzimmer_1-15,iPads-Lehrerzimmer_alle,iPads-Lehrerzimmer_16-30"
                except TypeError:
                    # print(groups_str)
                    groups_str += "," + ",".join(additional_groups)

                # Mapping von E-Mail zu Kürzel
                email_lower = user.email.lower()
                email_kuerzel = email_to_kuerzel.get(
                    email_lower, return_webuntis_uid(user)
                )

                # Definieren der Benutzerdaten für das CSV
                user_data_mapping = {
                    "Username": f"164501-{return_username(email_kuerzel, '', 'kurzform')}",
                    "Email": f"{return_username(email_kuerzel, '', 'kurzform')}@164501.nrw.schule",
                    "FirstName": email_kuerzel,
                    "LastName": email_kuerzel,
                    "TeacherGroups": groups_str,
                    "Groups": "AlleL",
                    "Password": return_initial_password(user),
                }

                # Schreiben der Benutzerdaten in das CSV
                f.write(
                    f"{user_data_mapping['Username']};{user_data_mapping['Email']};"
                    f"{user_data_mapping['FirstName']};{user_data_mapping['LastName']};"
                    f"{user_data_mapping['TeacherGroups']};{user_data_mapping['Groups']};"
                    f"{user_data_mapping['Password']}\n"
                )


def load_additional_groups_from_csv(file_path: str) -> list:
    additional_groups = []
    with open(file_path, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if 'additional_groups' in row:
                additional_groups_value = row['additional_groups']
                # Split groups if they are comma-separated
                additional_groups.extend(additional_groups_value.split(','))
    return additional_groups

def export_users_to_csv(users, file_name):
    with open(file_name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        # Schreibe CSV-Header
        writer.writerow(["given", "name", "username", "email", "kuerzel"])

        # Schreibe Benutzerdaten
        for user in users:
            writer.writerow(
                [
                    user.given,
                    user.name,
                    user.username,
                    user.email.lower(),
                    user.username,
                ]
            )


def export_groups_to_csv(groups, file_name):
    with open(file_name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        # Schreibe CSV-Header
        writer.writerow(["groupid", "parent", "name", "newname"])

        # Schreibe Gruppendaten
        for group in groups:
            writer.writerow([group.groupid, group.parent, group.name, shorten_group_name(group.name, group.groupid)])


def main_export_mapping(inputaktuell, exportdate):
    # Initialisiere leere Listen
    users = []
    groups = []
    memberships = []

    # Parse das XML
    tree = ET.parse(inputaktuell)
    print(tree)
    global schuljahr  # Stelle sicher, dass 'schuljahr' global sichtbar ist
    schuljahr = parse_year(inputaktuell).replace("/", "")
    root = tree.getroot()
    parse_xml(users, groups, memberships, root)

    # Exportiere Benutzer und Gruppen
    export_users_to_csv(users, f"users{exportdate}.csv")
    export_groups_to_csv(groups, f"groups{exportdate}.csv")

    print("CSV-Dateien wurden erfolgreich exportiert.")


def main_generate_accounts(users_csv, exportdate):
    # Lade die Email-zu-Kürzel-Zuordnung
    email_to_kuerzel = load_email_to_kuerzel(users_csv)
    print("Kürzel-Mapping wurde aus 'users.csv' geladen und kann nun verwendet werden.")

    # Lade das Mappinggroups
    mappinggroups_csv = f"groups{exportdate}.csv"
    if not os.path.isfile(mappinggroups_csv):
        print(
            f"Fehler: '{mappinggroups_csv}' existiert nicht. Bitte führe zuerst die 'export' Option aus."
        )
        return
    mappinggroups = load_mappinggroups(mappinggroups_csv)

    # Generiere die JAMF-Accounts für Lehrer
    output_csv_teachers = f"./csv/08-jamf{exportdate}.csv"

    # Lade Benutzer, Gruppen und Mitgliedschaften
    users = []
    groups = []
    memberships = []

    # Parse das XML erneut, um aktuelle Daten zu erhalten
    inputaktuell = "./xml/SchILD20241007.xml"
    tree = ET.parse(inputaktuell)
    root = tree.getroot()
    parse_xml(users, groups, memberships, root)

    # Rufe die angepasste Funktion auf und übergebe die geladenen Daten
    create_jamf_accounts_teachers(
        output_csv_teachers, email_to_kuerzel, users, groups, memberships, mappinggroups
    )

    print(f"Lehrer-Konten wurden in '{output_csv_teachers}' erstellt.")

    create_jamf_accounts(
        "06Ctest.csv",
        email_to_kuerzel,
        users,
        groups,
        memberships,
        mappinggroups,
        "06C",
    )


def main():
    parser = argparse.ArgumentParser(description="Schild2Jamf Skript mit Optionen.")
    parser.add_argument(
        "option",
        choices=["mapping", "accounts"],
        help="Option auswählen: 'export' zum Erstellen der CSV-Dateien, 'generate_kuerzel' zum Laden der Kürzel aus CSV.",
    )
    args = parser.parse_args()

    # Definiere den Pfad zur aktuellen XML-Datei
    inputaktuell = "./xml/SchILD20241007.xml"

    # Extrahiere das Datum aus dem Dateinamen
    exportdate = "".join([i for i in inputaktuell if i.isdigit()])

    if args.option == "mapping":
        main_export_mapping(inputaktuell, exportdate)
    elif args.option == "accounts":
        users_csv = f"users{exportdate}.csv"
        if not os.path.isfile(users_csv):
            print(
                f"Fehler: '{users_csv}' existiert nicht. Bitte führe zuerst die 'export' Option aus."
            )
            return
        main_generate_accounts(users_csv, exportdate)


if __name__ == "__main__":
    main()
