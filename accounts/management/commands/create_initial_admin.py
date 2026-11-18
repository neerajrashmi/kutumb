import getpass
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.core.exceptions import ValidationError
from genealogy.models import IndividualDetail
from accounts.models import UserDetail
from genealogy.validators import validate_individual_name


class Command(BaseCommand):
    help = "Creates the initial Individual (I0000001) and linked Admin UserDetail (I0000001)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("--- Initial Admin Account Setup ---"))

        # 1. Collect and validate Name according to Section 4.2
        while True:
            first_name = input("Enter First Name (A-Z/a-z/', no spaces): ").strip()
            middle_name = input("Enter Middle Name (optional, spaces allowed): ").strip()
            last_name = input("Enter Last Name (A-Z/a-z/', no spaces): ").strip()

            try:
                validate_individual_name(first_name, middle_name, last_name)
                break
            except ValidationError as e:
                self.stdout.write(self.style.ERROR(f"Validation Error: {e.messages[0]}"))

        # 2. Collect Gender
        while True:
            gender = input("Enter Gender [M/F/O]: ").strip().upper()
            if gender in ('M', 'F', 'O'):
                break
            self.stdout.write(self.style.ERROR("Invalid input. Choose M, F, or O."))

        # 3. Collect Password
        while True:
            password = getpass.getpass("Enter Admin Password: ")
            password_confirm = getpass.getpass("Confirm Admin Password: ")
            if not password:
                self.stdout.write(self.style.ERROR("Password cannot be blank."))
                continue
            if password != password_confirm:
                self.stdout.write(self.style.ERROR("Passwords do not match. Try again."))
                continue
            break

        # 4. Atomic creation of both Individual_Detail and User_Detail
        try:
            with transaction.atomic():
                # Creates I0000001 via IdSequence
                individual = IndividualDetail(
                    first_name=first_name,
                    middle_name=middle_name,
                    last_name=last_name,
                    gender=gender,
                )
                individual.save()

                # Creates User_Detail with User_Id == I0000001
                admin_user = UserDetail(
                    user_id=individual,
                    user_status='ACTIVE',
                    is_staff=True,
                    is_superuser=True,
                )
                admin_user.set_password(password)
                admin_user.save()

                # Set audit markers to self (I0000001)
                individual.created_by = individual.individual_id
                individual.modified_by = individual.individual_id
                individual.save(update_fields=['created_by', 'modified_by'])

                admin_user.created_by = individual.individual_id
                admin_user.modified_by = individual.individual_id
                admin_user.save(update_fields=['created_by', 'modified_by'])

                self.stdout.write(self.style.SUCCESS(
                    f"\nSuccessfully created Admin Individual and User account with ID: {individual.individual_id}"
                ))

        except Exception as exc:
            raise CommandError(f"Failed to create admin user: {str(exc)}")