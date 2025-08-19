import sys
sys.path.insert(0, './python_packages')
import smtplib
import dns.resolver
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import threading
import queue
import socks
import socket

NUM_THREADS = 150  # Fixer le nombre de threads à 150
BATCH_SIZE = 200   # Chaque batch contient 200 emails

# Définir SOCKS5 comme proxy
#socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 30005)
#socket.socket = socks.socksocket  # Remplacer le socket par celui qui passe par le proxy

def read_html_file(file_path):
    with open(file_path, "r", encoding="utf-8") as html_file:
        html_content = html_file.read()
    return html_content

def send_email_task(q, mx_server, sender_email, sender_name, subject, message, to_email):
    while True:
        batch = q.get()
        if batch is None:
            q.task_done()
            break  # Arrêter le thread quand on reçoit "None"

        try:
            server = smtplib.SMTP(mx_server)
            server.ehlo("noez.de")

            msg = MIMEMultipart()
            msg['From'] = formataddr((sender_name, sender_email))
            msg['To'] = to_email  # Affiche to_email en header, mais envoie à tous dans batch
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'html'))

            server.sendmail(sender_email, batch, msg.as_string())
            print("Batch of {} emails successfully sent.".format(len(batch)))

            server.quit()
        except Exception as e:
            print("Failed to send email batch: {}".format(e))
        finally:
            q.task_done()

def prepare_and_send_batches(recipient_emails, subject, message, sender_email, sender_name, to_email):
    domain = recipient_emails[0].split('@')[1]
    # Compatible with dnspython <2.0 (Python 3.6.x)
    try:
        mx_records = dns.resolver.query(domain, 'MX')
    except Exception as e:
        print("Could not resolve MX records: {}".format(e))
        return
    mx_record = sorted(mx_records, key=lambda rec: rec.preference)[0]
    mx_server = str(mx_record.exchange).rstrip('.')

    q = queue.Queue()

    # Créer les threads pour envoyer les e-mails
    threads = []
    for _ in range(NUM_THREADS):
        thread = threading.Thread(target=send_email_task, args=(q, mx_server, sender_email, sender_name, subject, message, to_email))
        thread.daemon = True
        thread.start()
        threads.append(thread)

    # Ajouter les emails dans la queue par batch de BATCH_SIZE
    for i in range(0, len(recipient_emails), BATCH_SIZE):
        batch = recipient_emails[i:i + BATCH_SIZE]
        q.put(batch)

    # Attendre que tous les emails soient envoyés
    q.join()

    # Envoyer un signal d'arrêt aux threads
    for _ in range(NUM_THREADS):
        q.put(None)
    
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    sender_email = "kundenservice@tkmedicakit.net"
    sender_name = "TK Medicare Kit"
    subject = "kostenloses Medicare Kit von der Techniker Krankenkasse"
    message = read_html_file("message.html")

    with open("mails.txt", "r") as file:
        recipient_emails = [line.strip() for line in file if line.strip()]

    to_email = "kundenservice@tkmedicakit.net"

    prepare_and_send_batches(recipient_emails, subject, message, sender_email, sender_name, to_email)
