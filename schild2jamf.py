# schild2jamf.py

import argparse
import xml.etree.ElementTree as ET
import mappings
import re
import utils
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
    """
    Parses user data from an XML structure and appends User objects to the provided list.

    This function iterates over XML elements representing persons. Each person element contains
    sub-elements with detailed information about teachers (faculty or extern) and students.

    For each user, the function:
    - Extracts user information, including ID, name, given name, email, and role.
    - Constructs a username based on the user's role:
      - For students, uses a short-form username.
      - For faculty or extern, uses a "vorname.nachname" format.
    - Checks for duplicate usernames and appends '1' to the username if a duplicate is found.
    - Calculates an initial password based on user attributes.
    - Extracts or formats additional user-specific details like birthday.
    - Creates a User object with the parsed data and appends it to the 'users' list.

    Args:
        users (list): A list to populate with User objects created from parsed XML data.

    Elements:
        - Person
          - id: Unique identifier for the user.
          - family: Last name of the user.
          - given: First name of the user.
          - institutionrole: Role of the user within the institution (Student, faculty, extern).
          - email: Email address of the user, if available.
          - bday: Birthday of the user, formatted as 'YYYY-MM-DD' for students.
    """
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
    """
    Parses group data from an XML structure and appends Group objects to
    the provided groups list.

    This function iterates over XML elements representing groups and extracts
    relevant information for each group. The parsed data includes:
    - The unique identifier for the group (groupid).
    - The name of the group, derived from its short description.
    - The parent group ID, if a hierarchical relationship exists between
      groups.

    The function then creates a Group object using the extracted data
    and appends it to the 'groups' list.

    Args:
        groups (list): A list to populate with Group objects created
                       from parsed XML data.

    XML Structure:
        - group
          - sourcedid
            - id: Unique identifier for the group.
          - description
            - short: Name of the group.
          - relationship
            - sourcedid
                - id: Unique identifier of the parent group (if any).
    """
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


def rename_groups(groups):
    """
    Renames groups based on various criteria extracted from their names.

    This function iterates over all groups and applies specific renaming rules
    based on the content and format of the group's `name` attribute. The renaming
    rules include:

    - If the group's name contains the word "Klasse", it processes the name to
      strip unwanted characters and appends the current school year (`schuljahr`).

    - If the group's name contains "BI8", it finds digits within the name,
      extracts content between parentheses, and reformats these components
      to create a new name pattern.

    - For group names containing general parentheses (not "BI8"), it extracts
      content within the parentheses and integrates parts into the new name
      structure, potentially incorporating identified digits.

    - Specifically renames groups containing 'Alle - Schueler' and 'Alle - Lehrer'
      by replacing these keywords with abbreviated forms.

    - Applies specific mappings for names containing "Fach" or "Bereich" using a
      predefined `mappings.mappinggroups`.

    Various transformations are performed on group names to shorten designations
    (e.g., replacing "Schueler" with "S" and "Lehrer" with "L"), and handle other
    formatting needs.

    This function assumes the presence of the `groups` list and `schuljahr` variable,
    along with a `mappings.mappinggroups` dictionary for specialized name conversion.
    """
    for group in groups:
        # Check if the group's name contains "Klasse"
        if "Klasse" in group.name:
            # Process the name by stripping unwanted characters and appending the school year
            group.name = (
                f'{group.name[7:].replace(" ", "").replace("Schueler", "S").replace("Lehrer", "L").replace("--", "").replace("-", "").replace(")", "").replace("UNESCO","U")}'
                + f"{schuljahr}"
            )

        # For groups involving "BI8" (assumed special processing)
        if "BI8" in group.name:
            # Find positions of parentheses in the name
            start = group.name.rfind("(")
            ende = group.name.rfind(")")
            try:
                # Search for a digit in the name outside the parentheses
                m = re.search(r"\d", group.name)
                digitfound = m.group(0)
            except:
                digitfound = ""

            # Extract content between parentheses, split and clean it
            templist = (
                group.name[start - 3 : ende]
                .replace(" ", "")
                .replace("(9", "")
                .split(",")
            )

            # Construct the new name based on refined components
            group.name = (
                f"{templist[0]}{templist[1] if templist[1] == 'GK' or templist[1] == 'LK' else ''}{digitfound if templist[1] == 'GK' or templist[1] == 'LK' else ''}{templist[2]}{templist[3]}".replace(
                    "Schueler", "S"
                )
                .replace("Lehrer", "L")
                .replace("--", "-")
                .replace(")", "")
                + f"{schuljahr}"
            )

        # General processing for names with parentheses that are not "BI8"
        elif "(" in group.name:
            # Find the start and end positions of the first set of parentheses
            start = group.name.rfind("(")
            ende = group.name.rfind(")")
            try:
                # Attempt to find a digit in the main part of the name
                m = re.search(r"\d", group.name)
                digitfound = m.group(0)
            except:
                digitfound = ""

            # Extract, process and split the content within parentheses
            templist = (
                group.name[start + 1 : ende]
                .replace(" ", "")
                .replace("UNESCO", "U")
                .split(",")
            )

            # Reassemble the new group name
            group.name = (
                f"{templist[0]}{templist[1] if templist[1] == 'GK' or templist[1] == 'LK' else ''}{digitfound if templist[1] == 'GK' or templist[1] == 'LK' else ''}{templist[2]}{templist[3]}".replace(
                    "Schueler", "S"
                )
                .replace("Lehrer", "L")
                .replace("--", "-")
                .replace(")", "")
                + f"{schuljahr}"
            )

        # Process specific group names containing "Alle - Schueler"
        if "Alle - Schueler" in group.name:
            group.name = (
                "Alle-Schueler".replace("Schueler", "S")
                .replace("Lehrer", "L")
                .replace(")", "")
                .replace("-", "")
            )

        # Process specific group names containing "Alle - Lehrer"
        if "Alle - Lehrer" in group.name:
            group.name = (
                "Alle-Lehrer".replace("Schueler", "S")
                .replace("Lehrer", "L")
                .replace(")", "")
                .replace("-", "")
            )

        # Map specialized names for groups containing "Fach"
        if "Fach" in group.name:
            group.name = mappings.mappinggroups[group.name]

        # Map specialized names for groups containing "Bereich"
        if "Bereich" in group.name:
            group.name = mappings.mappinggroups[group.name]


def parse_memberships(memberships, root):
    """
    Parses membership data from an XML structure and appends Membership objects
    to the provided memberships list.

    This function iterates over XML elements representing membership relationships,
    extracting necessary details for each membership, such as:
    - The unique identifier for the group (groupid) that the member is part of.
    - The unique identifier for the member (nameid) associated with the group.

    An internal counter 'i' is used to assign a unique membership ID for each
    relationship. For each parsed membership, the function creates a Membership
    object and appends it to the 'memberships' list.

    Args:
        memberships (list): A list to populate with Membership objects created
                            from parsed XML data.

    XML Structure:
        - membership
          - sourcedid
            - id: Unique identifier for the group.
          - member
            - sourcedid
                - id: Unique identifier of the member associated with the group.
    """
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
    """
    Parses XML data to populate lists of users, groups, and memberships.

    This function orchestrates the parsing of XML data to create objects for
    users, groups, and memberships from a specified XML structure. It calls
    separate parsing functions for each type of data:

    - Parses user-related XML data to create User objects and appends them
      to the provided 'users' list.
    - Parses group-related XML data to create Group objects and appends them
      to the provided 'groups' list.
    - Parses membership-related XML data to create Membership objects and
      appends them to the provided 'memberships' list.

    Args:
        users (list): A list to be populated with User objects parsed from the
                      XML data.
        groups (list): A list to be populated with Group objects parsed from the
                       XML data.
        memberships (list): A list to be populated with Membership objects parsed
                            from the XML data.
    """
    # Parse user data from the XML and populate the users list with User objects
    parse_users(users, root)

    # Parse group data from the XML and populate the groups list with Group objects
    parse_groups(groups, root)

    # Parse membership data from the XML and populate the memberships list with Membership objects
    parse_memberships(memberships, root)


def parse_year(xmlfile):
    """
    Parses the XML file to determine the school year format.

    This function tests for two potential year formats within the contents of the specified XML file:
    - The first format checks for the pattern '20ij/ij+1', where 'i' and 'j' are single digits representing the year.
    - The second format checks for '20ij/i+10', handling cases where the second half of the year spans a decade.

    The function iterates over combinations of 'i' and 'j' from '00' to '99', and searches for these formats.
    Once a matching format is found, it prints the matched year pattern and returns the starting year as a two-digit string.

    Args:
        xmlfile (str): The path to the XML file to be read and analyzed for determining the school year.

    Returns:
        str: A two-digit string representing the starting year of the identified school year format.
    """
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
    """
    Returns a WebUntis UID for a given user based on their attributes.

    This function generates a unique identifier for the WebUntis system
    using the user's given and last names or, alternatively, by slicing
    the user's LehrerID (teacher ID). The approach depends on the presence
    of the character 'X' in the LehrerID.

    Logic:
    - If the LehrerID contains 'X', it generates a UID using a short form
      of the user's name.
    - Otherwise, the UID is derived by taking a substring from the 11th
      character onwards from the LehrerID.

    Args:
        user: An instance of the User class.
    Returns:
        str: A string representing the WebUntis unique identifier for the user.
    """
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
    """
    Generates a username based on the specified type from given and last name strings.

    This function constructs a username in different formats depending on the `typ` argument provided:

    - If `typ` is "vorname.nachname", it creates a username by:
      - Translating the given name using a character mapping and taking the first token prior to any space.
      - Concatenating it with the translated last name (without spaces and hyphens) using a period as a separator.

    - If `typ` is "kurzform", it constructs a username by:
      - Translating the given name and extracting the first 4 characters.
      - Translating the last name (removing spaces and hyphens) and then taking its first 4 characters.

    The resulting username is returned in lowercase.

    Args:
        given (str): The given name to use in the username.
        last (str): The last name to use in the username.
        typ (str): The type of username to generate, either "vorname.nachname" or "kurzform".

    Returns:
        str: A generated username in lowercase.
    """
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
    """
    Removes hyphens from a given birthday string.

    This function takes a birthday string in the format 'YYYY-MM-DD' and
    returns a new string with all hyphens removed, effectively returning
    the birthday as 'YYYYMMDD'.

    Args:
        birthday (str): The birthday string containing hyphens to be stripped.

    Returns:
        str: The birthday string with hyphens removed.
    """
    return birthday.replace("-", "")


def return_initial_password(user):
    """
    Generates an initial password for a user based on specific attributes.

    This function constructs the initial password using snippets from the
    user's teacher ID, username, and birthday. The format of the password is
    a concatenation of the following components:
    - The last three characters from the user's teacher ID (lehrerid).
    - The last two characters from the user's username.
    - The first three characters from the birthday with hyphens removed.
    - The first two characters from the user's username.

    Args:
        user: An instance of the User class containing attributes needed for
              password generation (lehrerid, username, birthday).

    Returns:
        str: The assembled initial password comprising the concatenated parts
             derived from user's attributes.
    """
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
    """
    Retrieves a list of courses for a student based on their student ID.

    This function iterates through membership records to identify groups (courses)
    that a student is associated with, using the provided student ID. It attempts
    to map each membership to a group name from the list of known groups, collecting
    these names into a course list.

    If a group name is found, it is added to the list of courses for the student.
    An exception handling mechanism is in place to ensure that, in cases where a
    group's name cannot be found (possibly due to a mismatch or empty courses),
    the function will simply return an empty list.

    Args:
        studentid: A string representing the student ID used to lookup memberships.

    Returns:
        list: A list of strings representing the names of courses the student
              is enrolled in. If no courses are found or an error occurs, an
              empty list is returned.
    """
    # Initialize an empty list to store course names for a given student
    courseslist = []

    # Iterate over the group IDs the student is a member of, based on their student ID
    for course in [
        membership.groupid
        for membership in memberships
        if membership.nameid == studentid
    ]:
        try:
            # Attempt to find the first group name corresponding to the course ID
            groupname = [group.name for group in groups if group.groupid == course][0]

            # If a group name is found and it's not an empty string, add it to the courses list
            if groupname != "":
                courseslist.append(groupname)

        except:
            # If an exception occurs (likely due to the list being empty), return an empty courses list
            courseslist = []

    # Return the list of course names for the student
    return courseslist


def return_class_of_user(user, memberships):
    """
    Determines the class of a given user based on their LehrerID and a class mapping.

    This function first obtains a list of courses the user is enrolled in by calling
    `return_list_of_courses_of_student(user.lehrerid)`. It then uses a predefined
    mapping dictionary (`mappings.mappingklassen`) to map class identifiers to
    specific class names.

    The function iterates through each key (class identifier) in the mapping and
    checks if this class identifier, concatenated with the current school year
    (`schuljahr`), is present in the list of courses. If a match is found, the
    corresponding class name from the mapping is returned.

    Args:
        user: An instance of the User class for whom the class is being determined.

    Returns:
        str: The class name associated with the user if a match is found,
             otherwise None.
    """
    # Retrieve the list of courses the user is enrolled in based on their LehrerID
    klassen = return_list_of_courses_of_student(user.lehrerid, memberships)

    # Access the mapping dictionary that maps class identifiers to class names
    mappingklassen = mappings.mappingklassen

    # Iterate through each item in the class mapping
    for item in mappingklassen:
        # Check if the class identifier with the current school year is present in the user's courses
        if item + f"{schuljahr}" in klassen:
            # If found, return the corresponding class name from the mapping
            return mappingklassen[item]


def create_jamf_accounts(
    nameOfOutputCsv: str,
    dict_name_serial: dict,
    users,
    memberships,
    klasse_filter: str = None,
):
    """
    Generates a JAMF-compatible CSV file with account details for users, potentially
    filtered by class, and optionally includes device serial numbers.

    This function creates a CSV file for JAMF account creation based on user data. It can filter
    users by class if a `klasse_filter` is provided and if a corresponding class CSV file exists.
    The CSV file is augmented with serial numbers, drawn from a dictionary, if available.

    The output CSV will include headers for user credentials, including username, email, first name,
    last name, group assignments, password, and optionally, serial numbers. The function ensures
    proper handling of serial number assignments to users.

    Args:
        nameOfOutputCsv (str): The path and name of the output CSV file to be created.
        dict_name_serial (dict): A dictionary mapping names to serial numbers for device assignment.
        klasse_filter (str, optional): A filter string representing a class name to limit which users
                                       are included. Defaults to None.

    Writes:
        A CSV file at the specified path with the user and device serial number information,
        formatted for JAMF account provisioning.
    """
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
            if klasse_filter and return_class_of_user(user) != klasse_filter:
                continue

            # Retrieve user courses and formats them into groups
            courses = return_list_of_courses_of_student(user.lehrerid, memberships)
            groups = ",".join(courses)
            # Map user info to the specific CSV structure
            user_data_mapping = {
                "Username": f"164501-{user.username}",
                "Email": f"{user.username}@164501.nrw.schule",
                "FirstName": f"{user.username[:4]}",
                "LastName": f"{user.username[4:]}",
                "Groups": groups,
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
    nameOfOutputCsv: str, memberships, users, klasse_filter: str = None
):
    """
    Generates a JAMF-compatible CSV file specifically for teachers' accounts.

    This function creates a CSV file with account details for teachers by filtering users
    who belong to the "AlleL" (all teachers) group. It formats the user data to match
    JAMF requirements. The function processes and updates group assignments, constructing
    a list of teacher-specific or general access groups and altering specific group names
    to fit desired formats.

    The CSV content is tailored for a school management system, including headers and
    user credentials such as username, email, associated teacher and general groups,
    and an initial password. If any user has no email mapping available in the external
    mapping, a default WebUntis UID is generated.

    Args:
        nameOfOutputCsv (str): The path and name of the output CSV file to be created.
        klasse_filter (str, optional): Currently not used in this implementation but kept
                                       for interface consistency.

    Writes:
        A CSV file at the specified path with the teacher account information formatted for JAMF.
    """
    with open(nameOfOutputCsv, "w", encoding="utf-8") as f:
        # Write the header line to the output CSV file
        f.write("Username;Email;FirstName;LastName;TeacherGroups;Groups;Password\n")

        for user in users:
            # Get the list of courses for each user and convert to a CSV-friendly format
            courses = return_list_of_courses_of_student(user.lehrerid, memberships)
            groups = f'{"##".join(courses)}'.replace("##", ",")

            # Check if "AlleL" (assumed to mean 'all teachers') is in the group list
            if "AlleL" in groups:
                # Filter to select groups matching specific patterns (grades and levels)
                filtered_groups = []
                for group in groups.split(","):
                    if any(
                        substring in group for substring in ["09", "10", "EF", "Q1"]
                    ) and group not in ["EFL24", "Q1L24", "Q2L24"]:
                        filtered_groups.append(group)

                # Update group names by replacing 'L' with 'S' for specific grades
                updated_groups = []
                for group in filtered_groups:
                    if (
                        len(group) == 6
                        and group[0:2] in ["09", "10"]
                        and group[3] == "L"
                    ):
                        updated_groups.append(group[:3] + "S" + group[4:])
                    else:
                        updated_groups.append(group)
                groups = ",".join(updated_groups)
                groups = (
                    groups
                    + ",iPads-Lehrerzimmer_1-15,iPads-Lehrerzimmer_alle,iPads-Lehrerzimmer_16-30,FW-LZ-01-15,FW-LZ-16-30,FW-LZ-alle,FW-1.Stock-01-15,FW-1.Stock-16-30,FW-1.Stock-alle"
                )

                # Map user's email to a specific key or use an alternate ID
                try:
                    email_kuerzel = mappings.mapping_email_kuerzel[user.email]
                except KeyError:
                    email_kuerzel = return_webuntis_uid(user)

                # Define user data mapping for CSV output
                user_data_mapping = {
                    "Username": f"164501-{return_username(email_kuerzel, '', 'kurzform')}",
                    "Email": f"{return_username(email_kuerzel, '', 'kurzform')}@164501.nrw.schule",
                    "FirstName": email_kuerzel,
                    "LastName": email_kuerzel,
                    "TeacherGroups": groups,
                    "Groups": "AlleL",
                    "Password": return_initial_password(user),
                }

                # Write the user data line to the output file
                f.write(
                    f"{user_data_mapping['Username']};{user_data_mapping['Email']};{user_data_mapping['FirstName']};{user_data_mapping['LastName']};{user_data_mapping['TeacherGroups']};{user_data_mapping['Groups']};{user_data_mapping['Password']}\n"
                )


def load_email_to_kuerzel(users_csv):
    return mappings.load_email_to_kuerzel(users_csv)


def load_mappinggroups(mappinggroups_csv):
    return mappings.load_mappinggroups(mappinggroups_csv)


def create_jamf_accounts_teachers(
    nameOfOutputCsv: str,
    email_to_kuerzel: dict,
    users,
    memberships,
    klasse_filter: str = None,
):
    """
    Generates a JAMF-compatible CSV file specifically for teachers' accounts.
    """
    with open(nameOfOutputCsv, "w", encoding="utf-8") as f:
        # Schreiben der Kopfzeile
        f.write("Username;Email;FirstName;LastName;TeacherGroups;Groups;Password\n")

        for user in users:
            # Abrufen der Kurse des Lehrers
            courses = return_list_of_courses_of_student(user.lehrerid, memberships)
            groups = ",".join(courses)

            # Prüfen, ob "AlleL" in den Gruppen ist
            if "AlleL" in groups:
                # Filtern der Gruppen basierend auf bestimmten Kriterien
                filtered_groups = []
                for group in groups.split(","):
                    if any(
                        sub in group for sub in ["09", "10", "EF", "Q1"]
                    ) and group not in ["EFL24", "Q1L24", "Q2L24"]:
                        filtered_groups.append(group)

                # Aktualisieren der Gruppennamen
                updated_groups = []
                for group in filtered_groups:
                    if (
                        len(group) == 6
                        and group[0:2] in ["09", "10"]
                        and group[3] == "L"
                    ):
                        updated_groups.append(group[:3] + "S" + group[4:])
                    else:
                        updated_groups.append(group)
                groups = ",".join(updated_groups)
                groups += ",iPads-Lehrerzimmer_1-15,iPads-Lehrerzimmer_alle,iPads-Lehrerzimmer_16-30"

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
                    "TeacherGroups": groups,
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
        writer.writerow(["groupid", "parent", "name"])

        # Schreibe Gruppendaten
        for group in groups:
            writer.writerow([group.groupid, group.parent, group.name])


def main_export(inputaktuell, exportdate):
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

    # Benenne Gruppen um
    rename_groups(groups)

    # Exportiere erneut, falls Gruppen umbenannt wurden
    export_groups_to_csv(groups, f"groups_{exportdate}_renamed.csv")

    print("CSV-Dateien wurden erfolgreich exportiert.")


def main_generate_kuerzel(users_csv, exportdate):
    email_to_kuerzel = load_email_to_kuerzel(users_csv)
    print("Kürzel-Mapping wurde aus 'users.csv' geladen und kann nun verwendet werden.")

    # Lade das Mappinggroups
    mappinggroups_csv = f"groups_{exportdate}_renamed.csv"
    if not os.path.isfile(mappinggroups_csv):
        print(
            f"Fehler: '{mappinggroups_csv}' existiert nicht. Bitte führe zuerst die 'export' Option aus."
        )
        return
    mappinggroups = mappings.load_mappinggroups(mappinggroups_csv)

    # Aktualisiere das 'mappings.mappinggroups' Dictionary
    mappings.mappinggroups = mappinggroups

    # Generiere die JAMF-Accounts für Lehrer
    output_csv_teachers = f"./csv/08-jamf{exportdate}.csv"
    create_jamf_accounts_teachers(output_csv_teachers, email_to_kuerzel)

    print(f"Lehrer-Konten wurden in '{output_csv_teachers}' erstellt.")


def main():
    parser = argparse.ArgumentParser(description="Schild2Jamf Skript mit Optionen.")
    parser.add_argument(
        "option",
        choices=["export", "generate_kuerzel"],
        help="Option auswählen: 'export' zum Erstellen der CSV-Dateien, 'generate_kuerzel' zum Laden der Kürzel aus CSV.",
    )
    args = parser.parse_args()

    # Definiere den Pfad zur aktuellen XML-Datei
    inputaktuell = "./xml/SchILD20241007.xml"

    # Extrahiere das Datum aus dem Dateinamen
    exportdate = "".join([i for i in inputaktuell if i.isdigit()])

    if args.option == "export":
        main_export(inputaktuell, exportdate)
    elif args.option == "generate_kuerzel":
        users_csv = f"users{exportdate}.csv"
        if not os.path.isfile(users_csv):
            print(
                f"Fehler: '{users_csv}' existiert nicht. Bitte führe zuerst die 'export' Option aus."
            )
            return
        main_generate_kuerzel(users_csv, exportdate)


# =========================
# Main Block
# =========================


if __name__ == "__main__":
    main()


# if __name__ == "__main__":
#     # Set the path to the current XML file containing the user, group, and membership information
#     inputaktuell = "./xml/SchILD20241007.xml"

#     # Extract the date from the input file name by filtering digits
#     exportdate = "".join([i for i in inputaktuell if i.isdigit()])

#     # Print the extracted export date
#     print(exportdate)

#     # Initialize empty lists to store parsed data for users, groups, and memberships
#     users = []
#     groups = []
#     memberships = []

#     # Parse the XML file to build an ElementTree object
#     tree = ET.parse(inputaktuell)

#     # Determine the school year from the XML file and clean up the format
#     schuljahr = parse_year(inputaktuell).replace("/", "")

#     # Get the root element of the XML tree
#     root = tree.getroot()

#     # Parse the XML to populate the lists of users, groups, and memberships
#     parse_xml(users, groups, memberships)

#     # Rename groups based on preset rules and mappings
#     rename_groups()

#     # Generate a dictionary mapping names to device serial numbers
#     dict_name_serial = utils.get_dict_name_serial("devices20241010.csv")


#     # Generate CSV files for different classes based on a specific class filter
#     create_jamf_accounts(f"./csv/01-jamf{exportdate}.csv", dict_name_serial, "EF")
#     create_jamf_accounts(f"./csv/02-jamf{exportdate}.csv", dict_name_serial, "10b")
#     create_jamf_accounts(f"./csv/03-jamf{exportdate}.csv", dict_name_serial, "10a")
#     create_jamf_accounts(f"./csv/04-jamf{exportdate}.csv", dict_name_serial, "10c")
#     create_jamf_accounts(f"./csv/05-jamf{exportdate}.csv", dict_name_serial, "9a")
#     create_jamf_accounts(f"./csv/06-jamf{exportdate}.csv", dict_name_serial, "9b")
#     create_jamf_accounts(f"./csv/07-jamf{exportdate}.csv", dict_name_serial, "9c")
#     create_jamf_accounts(f"./csv/09-jamf{exportdate}.csv", dict_name_serial, "5c")

#     # Create a CSV for teacher accounts
#     create_jamf_accounts_teachers(f"./csv/08-jamf{exportdate}.csv", "None")

#     # Dies ist ein Test.
