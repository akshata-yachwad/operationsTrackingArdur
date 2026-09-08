import os
import django
import sys

# Ensure the script can import from apps
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "opstracking.settings.dev")
django.setup()

from apps.accounts.models import Employee, User, Role, EmployeeType
from django.contrib.auth.hashers import make_password

users_data = [
    ("Lalita Varkade", "ATS0108", "ardur123"),
    ("Shubham Bhivsane", "AT0048", "Shubhu@48"),
    ("Poonam Baraskar", "ATS0105", "ardur123"),
    ("Komal Rathore", "ATS0006", "ardur123"),
    ("Bhagyashri Chadokar", "ATS0008", "ardur123"),
    ("Sonali Prajapati", "ATS0009", "ardur123"),
    ("Neha Makode", "ATS0010", "ardur123"),
    ("Shaifali Malviya", "ATS0011", "ardur123"),
    ("Samiksha Kalsule", "ATS0012", "ardur123"),
    ("Pooja Barai", "ATS0021", "ardur123"),
    ("Vaishali Malvi", "ATS0016", "ardur123"),
    ("Yogesh Chouhan", "ATS0020", "ardur123"),
    ("Shweta Kumbhare", "ATS0022", "ardur123"),
    ("Aarti Mahski", "ATS0023", "Niaa1231"),
    ("Priyesh Jain", "ATS0030", "12345"),
    ("Jyoti Maheshwari", "ATS0033", "ardur123"),
    ("Balram Bisar", "ATS0040", "babu@22"),
    ("Kanchi Bankar", "ATS0048", "k2000"),
    ("Divya Dounde", "ATS0049", "divya123"),
    ("Pusplata Dounde", "ATS0050", "ardur123"),
    ("Nikita Dhadse", "ATS0053", "basnerkala"),
    ("Ritika Denge", "ATS0056", "ardur123"),
    ("Sukhvanti Uikey", "ATS0057", "ardur123"),
    ("Divya Lokhande", "ATS0060", "ardur123"),
    ("Sonali Dange", "ATS0064", "ardur123"),
    ("Seema Kushwaha", "ATS0068", "ladoo@28"),
    ("Dhramendra Gangare", "ATS0070", "ardur123"),
    ("Neeraj Dhurve", "ATS0072", "Neeraj@93"),
    ("Nikita Bamgude", "AT0051", "India$123"),
    ("Nidhi Gurung", "AT0052", "ardur123"),
    ("Sakshi Mahadik", "AT0061", "ardur123"),
    ("Gayatri More", "AT0087", "ardur123"),
    ("Rasika Rajendra More", "AT0088", "ardur123"),
    ("Rakhi Mujmule", "AT0097", "ardur123"),
    ("Yatin Badgujar", "AT0019", "ardur123"),
    ("Nikita Barsakar", "ATS0076", "ardur123"),
    ("Mangesh Dagade", "AT0157", "ardur@123"),
    ("Beena Uikey", "ATS0082", "Beena1004"),
    ("Preeti Deshmukh", "ATS0083", "ardur123"),
    ("Pratima Khakre", "ATS0045", "997720"),
    ("Kajal Pandagre", "ATS0046", "nivi123"),
    ("Poonam Dighekar", "ATS0084", "ardur123"),
    ("Shivani Dhote", "ATS0095", "ardur123"),
    ("Seema Dhurve", "ATS0096", "ardur123"),
    ("Shalu Likhitkar", "ATS0097", "ardur123"),
    ("Monika Malviya", "ATS0098", "ardur123"),
    ("Chakori Gavhade", "ATS0099", "ardur123"),
    ("Sneha Malviya", "ATS0100", "ardur123"),
    ("Devika Sable", "ATS0101", "ardur123"),
    ("Pratiksha Dange", "ATS0104", "ardur123"),
    ("Kiran Sonawane", "AT0231", "ardur123"),
    ("Ritesh Sable", "ATS0019", "hariom"),
    ("Shivani Deshmukh", "ATS0118", "ardur123"),
    ("Saloni Deshmukh", "ATS0119", "ardur123"),
    ("Deepak Pawar", "ATS0121", "ardur123"),
    ("Kanchana Dhote", "ATS0123", "ardur123"),
    ("Ranu Chouhan", "ATS0124", "ardur123"),
    ("Rama Uikey", "ATS0125", "ardur123"),
    ("Jyoti Arya", "ATS0126", "ardur123"),
    ("Bhumika Fate", "ATS0127", "ardur123"),
    ("Muskan Satpute", "ATS0128", "ardur123"),
    ("Pragya Chauhan", "ATS0129", "ardur123"),
    ("Shivani Garge", "ATS0131", "ardur123"),
    ("Shivani Yadav", "ATS0132", "ardur123"),
    ("Nidhi Deshmukh", "ATS0133", "ardur123"),
    ("Ankita Kapse", "ATS0134", "ardur123"),
    ("Maheshwari Rajput", "ATS0135", "ardur123"),
    ("Tusha Pawar", "ATS0136", "ardur123"),
    ("Dimpal Makode", "ATS0137", "ardur123"),
    ("Preetika Uikey", "ATS0138", "ardur123"),
    ("Ayushi Jhod", "ATS0139", "ardur123"),
    ("Vivek Yadav", "ATS0140", "ardur123"),
    ("Nilu Banwari", "ATS0141", "ardur123"),
    ("Arpita chadhokr", "ATS0142", "ardur123"),
    ("Chetna Sahu", "ATS0143", "ardur123"),
    ("Karishma Suryavanshi", "ATS0144", "ardur123"),
    ("Anjali Panse", "ATS0145", "ardur123"),
    ("Neha Magarde", "ATS0146", "ardur123"),
    ("Akshara Kumre", "ATS0147", "ardur123"),
    ("Amisha Dhadse", "ATS0148", "ardur123"),
    ("Neelam Dhadse", "ATS0149", "ardur123"),
    ("Kratika Dabde", "ATS0150", "ardur123"),
    ("Jyoti Pawar", "ATS0151", "ardur123"),
    ("Babita Dabde", "ATS0152", "ardur123"),
]

def add_users():
    for name, emp_id, pwd in users_data:
        # Create or update Employee
        emp, created = Employee.objects.update_or_create(
            employee_id=emp_id,
            defaults={
                "name": name,
                "role": Role.EMPLOYEE,
                "project": "TITLE INDEXING",
                "client_code": "DEFAULT",
                "work_type": "INDEXING",
                "employee_type": EmployeeType.EMPLOYEE,
            }
        )
        print(f"{'Created' if created else 'Updated'} Employee: {name} ({emp_id})")
        
        # Create or update User
        user, u_created = User.objects.update_or_create(
            emp_id=emp_id,
            defaults={
                "name": name,
                "password": make_password(pwd),
                "status": "active",
            }
        )
        print(f"{'Created' if u_created else 'Updated'} User login for: {emp_id}")

if __name__ == "__main__":
    add_users()
