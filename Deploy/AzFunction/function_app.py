import os
import logging

import azure.functions as func
from azure.data.tables import TableServiceClient
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Global variables
SENDGRID_API_KEY = None
TABLE_SERVICE_CONNECTION_STRING = None
SENDER_EMAIL = "no-replys@bhsconsulting.fr"
RECIPIENT_MAIL = "paul.bourhis@bhsconsulting.fr"


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def send_email(subject, body):
    """
    Send an email using SendGrid
    """
    message = Mail(
        from_email=SENDER_EMAIL,
        to_emails=RECIPIENT_MAIL,
        subject=subject,
        plain_text_content=body,
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logging.info("Email sent successfully.")
    except Exception as e:
        logging.info("Error sending email:", str(e))
        return False
    else:
        return True


@app.route(route="HttpTrigger", methods=["POST"])
def HttpTrigger(
    req: func.HttpRequest,
) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    global SENDGRID_API_KEY
    SENDGRID_API_KEY = os.environ.get("CUSTOMCONNSTR_SendGridApiKey")

    if not SENDGRID_API_KEY:
        logging.warning("Missing environment variables")
        return func.HttpResponse("Missing environment variables", status_code=500)
    

    logging.info(req.form)
    name, mail, phone, company, message = (
        req.form.get("name"),
        req.form.get("email"),
        req.form.get("phone"),
        req.form.get("company"),
        req.form.get("message"),
    )

    logging.info(f"SENDGRID_API_KEY: {SENDGRID_API_KEY}")

    subject = f"You just received a message from {mail} from bhsconsulting.fr"
    body = f"""
        Name: {name}\n
        Mail: {mail}\n
        Phone: {phone}\n\n
        Company: {company}\n\n
        Message: {message}\n
    """

    res = send_email(subject, body)

    if res:
        return func.HttpResponse(
            "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
            status_code=200,
        )
    else:
        return func.HttpResponse(
            "Error sending email",
            status_code=500,
        )


@app.route(route="HttpTriggerNewMail", methods=["GET", "POST"])
def HttpTriggerNewMail(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    global SENDGRID_API_KEY, TABLE_SERVICE_CONNECTION_STRING
    SENDGRID_API_KEY = os.environ.get("CUSTOMCONNSTR_SendGridApiKey")
    TABLE_SERVICE_CONNECTION_STRING = os.environ.get("CUSTOMCONNSTR_TableServiceConnectionString")

    if not all([SENDGRID_API_KEY, TABLE_SERVICE_CONNECTION_STRING]):
        logging.warning("Missing environment variables")
        return func.HttpResponse("Missing environment variables", status_code=500)

    email = req.form.get("email")
    logging.info(f"New email is: {email}")

    if email:
        table_service_client = TableServiceClient.from_connection_string(
            conn_str=TABLE_SERVICE_CONNECTION_STRING
        )
        table_client = table_service_client.get_table_client(
            table_name="subscribersTable"
        )

        # Check for duplicate entries
        if email_exists(table_client, email):
            logging.warning(f"Duplicate email address: {email}")
            return func.HttpResponse("Email address already exists", status_code=400)

        # Add email to Azure Table Storage
        add_email_to_table(table_client, email)
        logging.info(f"Successfully registered email: {email}")

        res = send_email(
            subject=f"BHS Consulting - New subscriber",
            body=f"{email} want's to get notified when you're free",
        )

        if res:
            return func.HttpResponse(
                f"Successfully registered email: {email}",
                status_code=200,
            )
        else:
            return func.HttpResponse(
                "Error sending email",
                status_code=500,
            )
    else:
        logging.warning("No email address provided")
        return func.HttpResponse("Please provide an email address", status_code=400)


@app.route(route="HelloWorld", methods=["GET", "POST"])
def HelloWorld(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("HelloWorld function processed a request.")
    email = req.form.get("email")
    logging.info(f"New email is: {email}")

    return func.HttpResponse(
        "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
        status_code=200,
    )

 
def email_exists(table_client, email):
    # Check if the email address already exists in Azure Table Storage
    logging.info(f"Checking if email address exists: {email}")
    filter_condition = f"Email eq '{email}'"
    entities = table_client.query_entities(filter_condition)
    return any(entities)


def add_email_to_table(table_client, email):
    logging.info(f"Adding {email} to Azure Table Storage")
    # Create a new entity
    subscriber_entity = {
        "PartitionKey": "Subscribers",
        "RowKey": email,
        "Email": email,
        "SusbribedNewsletter": True,
    }
    table_client.create_entity(subscriber_entity)
