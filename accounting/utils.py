#!/user/bin/env python2.7
import logging
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from accounting import db
from models import Contact, Invoice, Payment, Policy

"""
#######################################################
This is the base code for the engineer project.
#######################################################
"""

class PolicyAccounting(object):
    """
     Each policy has its own instance of accounting.
    """
    def __init__(self, policy_id):
        self.policy = Policy.query.filter_by(id=policy_id).one()

        if not self.policy.invoices:
            self.make_invoices()
    """Updating billing schedule"""

    def update_billing_schedule(self, new_schedule=None):

        billing_schedules = {'Annual': None, 'Semi-Annual': 3, 'Quarterly': 4, 'Monthly': 12, 'Two-Pay': 2}
        """
        Check If the selected new schedule doesn't exist in our billing_schedules
        or if the policy is already updated with the requested schedule
        """
        if (self.policy.billing_schedule == new_schedule or not billing_schedules.has_key(new_schedule)):
            print "Please Choose one of these Valid billing Schedules:"
            for key, val in billing_schedules.iteritems():
                print key
            return

        """Updating old Invoices to Deleted status """
        for invoice in self.policy.invoices:
            invoice.deleted = True
        db.session.commit()

        """Update the new Billing Schedule"""
        self.policy.billing_schedule = new_schedule
        self.make_invoices()


    def return_account_balance(self, date_cursor=None):
        """
        if date_cursor is null
        then Initialize date_cursor with the current date
        """
        if not date_cursor:
            date_cursor = datetime.now().date()
        """
        return the invoices by policy_id where their bill_date less or equal to the date_cursor,
        ordered by the invoice bill date
        """
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.bill_date <= date_cursor)\
                                .filter(Invoice.deleted == False)\
                                .order_by(Invoice.bill_date)\
                                .all()

        # get the sum of the due amount
        due_now = 0
        for invoice in invoices:
            due_now += invoice.amount_due

        """
        Get all the payments by policy_id
        where it's transaction_date less or equal to the date_cursor
        """
        payments = Payment.query.filter_by(policy_id=self.policy.id)\
                                .filter(Payment.transaction_date <= date_cursor)\
                                .all()

        """
        substracting the paid payments from the total due amount
        """
        for payment in payments:
            due_now -= payment.amount_paid

        return due_now

    def make_payment(self, contact_id=None, date_cursor=None, amount=0):
        """
        if date_cursor is null
        then Initialize date_cursor with the current date
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        """
        If contact_id is NULL then contact_id = named_insured
        """
        if not contact_id:
            try:
                contact_id = self.policy.named_insured
            except:
                logging.exception("contact_id cannot be NULL")
                return

        if self.evaluate_cancellation_pending_due_to_non_pay(date_cursor):
            contact = Contact.query.filter_by(id=contact_id).one()
            if 'Agent' != contact.role:
                print 'At This Stage, Only an agent can make the payment.'
                return

        """
        Creating a new payment with the previous Information and persisting it
        """
        payment = Payment(self.policy.id,
                          contact_id,
                          amount,
                          date_cursor)
        db.session.add(payment)
        db.session.commit()

        return payment

    def evaluate_cancellation_pending_due_to_non_pay(self, date_cursor=None):
        """
         If this function returns true, an invoice
         on a policy has passed the due date without
         being paid in full. However, it has not necessarily
         made it to the cancel_date yet.
        """
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.deleted == False)\
                                .order_by(Invoice.bill_date)\
                                .all()

        # get invoices payments
        for invoice in invoices:
            payments = Payment.query.filter_by(policy_id=invoice.policy_id)\
                                    .filter(Payment.transaction_date <= invoice.due_date and Payment.transaction_date >= invoice.bill_date)\
                                    .all()
            if not payments:
                if date_cursor < invoice.cancel_date and date_cursor > invoice.due_date:
                    return True

        return False

    def evaluate_cancel(self, date_cursor=None):

        """
        If date_cursor is NULL, Initialize it with the current date
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        """
        Get all Invoices by policy_id where the cancel_date less or equal to the date_cursor
        ordered by the bill_date
        """
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.cancel_date <= date_cursor)\
                                .filter(Invoice.deleted == False)\
                                .order_by(Invoice.bill_date)\
                                .all()

        """
        Check if Policy should be cancelled or not and printing the result
        by checking if there is a remaining unpaid balance or not
        """
        for invoice in invoices:
            if not self.return_account_balance(invoice.cancel_date):
                continue
            else:
                print "THIS POLICY SHOULD HAVE CANCELED"
                self.cancel_policy("unpaid", "This has an Unpaid Invoice", datetime.now().date())
                return True
        else:
            print "THIS POLICY SHOULD NOT CANCEL"
            return False

    """
    This Method cancel a policy with it's full descriptions.
    ps: all cancel info are required (By choice), to chane it edit the conditional statements
    """
    def cancel_policy(self, cancel_reason=None, cancel_desc=None, cancel_date=None):
        """
        All available cancalation reasons
        """
        cancelation_reason = ["underwriting", "unpaid", 'unauthorized']

        """
        Check whether a cancel status or the cancel description, it's status is not null
        """
        if not cancel_reason or not cancel_desc :
            print "In order to cancel a policy, you should enter it's cancelation status and it's description"
            return

        """
        Check if cancel reason is valid
        """
        if  not cancelation_reason.__contains__(cancel_reason):
            print "please choose one of these cancelation reasons:"
            for val in cancelation_reason:
                print val
            return False

        if not cancel_date:
            cancel_date = datetime.now().date()

        self.policy.status = 'Canceled'
        self.policy.cancelation_date = cancel_date
        self.policy.cancellation_description = cancel_desc
        self.policy.cancelation_reason = cancel_reason

        """
        marking the policy's invoices as deleted
        """
        for invoice in self.policy.invoices:
            invoice.deleted = True

        db.session.commit()


    def make_invoices(self):
        """
        Deleting the policy invoices
        """
        for invoice in self.policy.invoices:
            if invoice.deleted == False:
                invoice.delete()
        #Creating a dictionary for the billing_schedules
        billing_schedules = {'Annual': None, 'Semi-Annual': 3, 'Quarterly': 4, 'Monthly': 12, 'Two-Pay': 2}
        """
        Creating the Policy's Invoice with it's effective dates
        """
        invoices = []
        first_invoice = Invoice(self.policy.id,
                                self.policy.effective_date, #bill_date
                                self.policy.effective_date + relativedelta(months=1), #due
                                self.policy.effective_date + relativedelta(months=1, days=14), #cancel
                                self.policy.annual_premium)
        invoices.append(first_invoice)

        """
        Creating the remaining invoices for the different types of billing_schedule
        """

        if not billing_schedules.has_key(self.policy.billing_schedule):
            """
            Wrong schedule, No invoice will be created for it
            """
            print "You have chosen a bad billing schedule."
            return

        if self.policy.billing_schedule == "Annual":
            pass
        else:
            first_invoice.amount_due = first_invoice.amount_due / billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy.billing_schedule)):
                if self.policy.billing_schedule == "Two-Pay":
                    months_after_eff_date = i*6
                elif self.policy.billing_schedule == "Quarterly":
                    months_after_eff_date = i*3
                elif self.policy.billing_schedule == "Monthly":
                    months_after_eff_date = i
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  self.policy.annual_premium / billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)

        """
        Looping throught the Invoices and persisting each one
        """
        for invoice in invoices:
            db.session.add(invoice)
        db.session.commit()


################################
# The functions below are for the db and
# shouldn't need to be edited.
################################
def build_or_refresh_db():
    db.drop_all()
    db.create_all()
    insert_data()
    print "DB Ready!"

def insert_data():
    #Contacts
    contacts = []
    john_doe_agent = Contact('John Doe', 'Agent')
    contacts.append(john_doe_agent)
    john_doe_insured = Contact('John Doe', 'Named Insured')
    contacts.append(john_doe_insured)
    bob_smith = Contact('Bob Smith', 'Agent')
    contacts.append(bob_smith)
    anna_white = Contact('Anna White', 'Named Insured')
    contacts.append(anna_white)
    joe_lee = Contact('Joe Lee', 'Agent')
    contacts.append(joe_lee)
    ryan_bucket = Contact('Ryan Bucket', 'Named Insured')
    contacts.append(ryan_bucket)

    for contact in contacts:
        db.session.add(contact)
    db.session.commit()

    policies = []
    p1 = Policy('Policy One', date(2015, 1, 1), 365)
    p1.billing_schedule = 'Annual'
    p1.named_insured = anna_white.id
    p1.agent = bob_smith.id
    policies.append(p1)

    p2 = Policy('Policy Two', date(2015, 2, 1), 1600)
    p2.billing_schedule = 'Quarterly'
    p2.named_insured = anna_white.id
    p2.agent = joe_lee.id
    policies.append(p2)

    p3 = Policy('Policy Three', date(2015, 1, 1), 1200)
    p3.billing_schedule = 'Monthly'
    p3.named_insured = ryan_bucket.id
    p3.agent = john_doe_agent.id
    policies.append(p3)

    p4 = Policy('Policy Four', date(2015, 2, 1), 500)
    p4.billing_schedule = 'Two-Pay'
    p4.named_insured = ryan_bucket.id
    p4.agent = john_doe_agent.id
    policies.append(p4)

    for policy in policies:
        db.session.add(policy)
    db.session.commit()

    for policy in policies:
        PolicyAccounting(policy.id)

    payment_for_p2 = Payment(p2.id, anna_white.id, 400, date(2015, 2, 1))
    db.session.add(payment_for_p2)
    db.session.commit()
