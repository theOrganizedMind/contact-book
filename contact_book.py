from tkinter import Tk, Label, Entry, Button, ttk
import tkinter as tk
import os
import logging
import requests
from dotenv import load_dotenv

from postgresql import get_db_connection


# ========================================================================== #
# ================================ INFO ==================================== #
# ========================================================================== #
# Adds and Searches for contacts stored in a PostgreSQL database. 
# ========================================================================== #
# ================================ TODO ==================================== #
# ========================================================================== #
# TODO: 
# ========================================================================== #

load_dotenv()

GOOGLE_MAPS_API = os.getenv("GOOGLE_MAPS_API")

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contact_book.log")
logger = logging.getLogger("contact_book")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(file_handler)
    logger.propagate = False


class ContactBook:
    """
    ContactBook class for managing contacts in PostgreSQL.

    This class provides methods to add, update, remove, search, and select 
    contacts. The contact data is stored in a JSON file, and the user can 
    interact with the data through a graphical interface.

    Attributes:
    - filtered_contacts (list): List of contacts filtered by search criteria.
    """
    def __init__(self):
        """
        Initialize the ContactBook class.

        This method sets up the initial state of the ContactBook class and an
        empty list for filtered contacts.
        """
        self.filtered_contacts = []

        self.FONT = "Times New Roman"
        self.FONT_SIZE = 13
        self.TITLE_FONT = "Arial"
        self.TITLE_FONT_SIZE = 16

    def open_contact_book(self, company_var, billing_address_var, 
                          contact_name_var, phone_var, email_var):
        """
        Open the Contact Book Window.

        This function creates a new window for managing contacts. It allows the user
        to add, update, remove, search, and select contacts. The contact data is stored
        in PostgreSQL tables (client and company), and the user can interact with the
        data through a graphical interface.

        Features:
        - Add a new contact with company name, client name, phone number, and email.
        - Update an existing contact's details.
        - Remove a contact from the contact book.
        - Search for contacts by company name or client name.
        - Select a contact to populate fields in the main GUI.

        Parameters:
        None

        Returns:
        None
        """

        def parse_billing_address(address_value):
            """Split Billing Address into street, city, state, zip by commas."""
            parts = [part.strip() for part in address_value.split(",")]
            if len(parts) != 4 or any(not part for part in parts):
                return None
            return parts[0], parts[1], parts[2], parts[3]


        def normalize_address_from_components(address_components):
            """Normalize Google components into street, city, state, zip."""
            component_map = {}
            for component in address_components:
                for comp_type in component.get("types", []):
                    component_map[comp_type] = component

            street_number = component_map.get("street_number", {}).get("long_name", "")
            route = component_map.get("route", {}).get("long_name", "")
            subpremise = component_map.get("subpremise", {}).get("long_name", "")

            street_parts = [part for part in [street_number, route] if part]
            street = " ".join(street_parts).strip()
            if subpremise:
                street = f"{street} #{subpremise}" if street else f"#{subpremise}"

            city = (
                component_map.get("locality", {}).get("long_name")
                or component_map.get("postal_town", {}).get("long_name")
                or component_map.get("sublocality", {}).get("long_name")
                or ""
            )
            state = component_map.get("administrative_area_level_1", {}).get("short_name", "")
            zip_code = component_map.get("postal_code", {}).get("long_name", "")

            if not all([street, city, state, zip_code]):
                return None

            return street, city, state, zip_code


        def fetch_google_address_suggestions(query_text):
            """Fetch billing-address suggestions from Google Places Autocomplete."""
            if not GOOGLE_MAPS_API or not query_text:
                return []

            try:
                response = requests.get(
                    "https://maps.googleapis.com/maps/api/place/autocomplete/json",
                    params={
                        "input": query_text,
                        "types": "address",
                        "components": "country:us",
                        "key": GOOGLE_MAPS_API,
                    },
                    timeout=5,
                )
                response.raise_for_status()
                payload = response.json()

                return [
                    {
                        "place_id": prediction.get("place_id"),
                        "description": prediction.get("description", ""),
                    }
                    for prediction in payload.get("predictions", [])
                    if prediction.get("place_id") and prediction.get("description")
                ]
            except Exception:
                return []


        def fetch_normalized_address_by_place_id(place_id):
            """Resolve a place_id into Billing Address formatted as street, city, state, zip."""
            if not GOOGLE_MAPS_API or not place_id:
                return None

            try:
                response = requests.get(
                    "https://maps.googleapis.com/maps/api/place/details/json",
                    params={
                        "place_id": place_id,
                        "fields": "address_component",
                        "key": GOOGLE_MAPS_API,
                    },
                    timeout=5,
                )
                response.raise_for_status()
                payload = response.json()
                result = payload.get("result", {})
                address_components = result.get("address_components", [])

                normalized = normalize_address_from_components(address_components)
                if not normalized:
                    return None

                street, city, state, zip_code = normalized
                return f"{street}, {city}, {state}, {zip_code}"
            except Exception:
                return None


        def split_client_name(client_name):
            """Split full client name into first_name and last_name."""
            name_parts = client_name.strip().split(maxsplit=1)
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            return first_name, last_name


        def format_billing_address(street, city, state, zip_code):
            """Format PostgreSQL address columns into a single GUI string."""
            values = [street or "", city or "", state or "", zip_code or ""]
            return ", ".join(values)


        def fetch_contacts_from_postgresql(company_id=None, company_name=None, client_name=None):
            """Fetch joined client + company data for the contact list."""
            query = """
                SELECT
                    c.client_id,
                    c.company_id,
                    co.company_name,
                    co.street,
                    co.city,
                    co.state,
                    co.zip,
                    c.first_name,
                    c.last_name,
                    c.phone,
                    c.email
                FROM client c
                JOIN company co ON c.company_id = co.company_id
            """
            params = []
            conditions = []

            if company_id is not None:
                conditions.append("c.company_id = %s")
                params.append(company_id)
            if company_name:
                conditions.append("co.company_name ILIKE %s")
                params.append(f"%{company_name}%")
            if client_name:
                conditions.append("CONCAT_WS(' ', c.first_name, c.last_name) ILIKE %s")
                params.append(f"%{client_name}%")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY co.company_name, c.last_name, c.first_name;"

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    rows = cur.fetchall()

            contacts = []
            for row in rows:
                client_full_name = " ".join(part for part in [row[7], row[8]] if part).strip()
                contacts.append(
                    {
                        "client_id": row[0],
                        "company_id": row[1],
                        "company": row[2] or "N/A",
                        "billing address": format_billing_address(row[3], row[4], row[5], row[6]),
                        "client": client_full_name if client_full_name else "N/A",
                        "phone": row[9] or "N/A",
                        "email": row[10] or "N/A",
                    }
                )
            return contacts


        def update_or_insert_company(company_id, company_name, street, city, state, zip_code):
            """Update existing company row or insert a new one by company_id."""
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM company WHERE company_id = %s;", (company_id,))
                    exists = cur.fetchone() is not None

                    if exists:
                        cur.execute(
                            """
                            UPDATE company
                            SET company_name = %s, street = %s, city = %s, state = %s, zip = %s
                            WHERE company_id = %s;
                            """,
                            (company_name, street, city, state, zip_code, company_id),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO company (company_id, company_name, street, city, state, zip)
                            VALUES (%s, %s, %s, %s, %s, %s);
                            """,
                            (company_id, company_name, street, city, state, zip_code),
                        )
                conn.commit()


        def get_next_company_id():
            """Return the next available company_id for a new company."""
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COALESCE(MAX(company_id), 0) + 1 FROM company;")
                    return cur.fetchone()[0]


        def get_selected_contact():
            """Return selected contact index and record from current view."""
            selected_item = contact_list.selection()
            if not selected_item:
                return None, None

            item_index = int(selected_item[0])
            contacts = self.filtered_contacts if self.filtered_contacts else fetch_contacts_from_postgresql()
            if item_index >= len(contacts):
                return None, None

            return item_index, contacts[item_index]

        def show_toast(message, message_type="info"):
            """
            Show a toast-like notification.

            Parameters:
            message (str): The message to display.
            message_type (str): The type of message ("info", "warning", "error").

            Returns:
            None
            """
            toast = tk.Toplevel(contact_book_window)
            toast.overrideredirect(True)  # Remove window decorations
            toast.geometry("600x50+500+300")  # Set size and position
            toast.attributes("-topmost", True)  # Keep on top

            # Set background color based on message type
            bg_color = "green" if message_type == "info" else "orange" if message_type == "warning" else "red"
            # tk.Label(toast, text=message, bg=bg_color, fg="white", font=(FONT, FONT_SIZE)).pack(fill="both", expand=True)

            # fg_color = "green" if message_type == "info" else "orange" if message_type == "warning" else "red"
            tk.Label(toast, text=message, bg=bg_color, fg="black", 
                     font=(self.FONT, self.FONT_SIZE)).pack(fill="both", expand=True)

            # Use a Tcl-level `after` script so teardown does not try to invoke
            # a deleted Python callback command during window shutdown.
            toast.tk.call("after", 3000, f"catch {{destroy {toast._w}}}")


        def clear_fields():
            """
            Clear the input fields.

            This function clears the values in the company, client, phone, and email 
            entry widgets.

            Parameters:
            None

            Returns:
            None
            """
            entry_company_id.delete(0, tk.END)
            combo_company.set('')
            entry_billing_address.delete(0, tk.END)
            hide_address_suggestions()
            entry_client.delete(0, tk.END)
            entry_phone.delete(0, tk.END)
            entry_email.delete(0, tk.END)


        def add_contact():
            """
            Add a new contact to the contact book.
            """
            company_id_value = entry_company_id.get().strip()
            company_name = combo_company.get().strip()
            billing_address = entry_billing_address.get().strip()
            client_name = entry_client.get().strip()
            phone = entry_phone.get().strip()
            email = entry_email.get().strip()

            if not company_name or not billing_address or not client_name or not phone:
                show_toast("Company, Billing Address, Client Name, and Phone are required!", "warning")
                return

            if company_id_value and not company_id_value.isdigit():
                show_toast("Company ID must be a number.", "warning")
                return

            address_parts = parse_billing_address(billing_address)
            if not address_parts:
                show_toast("Billing Address must be: street, city, state, zip", "warning")
                return

            first_name, last_name = split_client_name(client_name)
            if not first_name:
                show_toast("Client Name is required.", "warning")
                return

            company_id = int(company_id_value) if company_id_value else get_next_company_id()
            street, city, state, zip_code = address_parts

            try:
                update_or_insert_company(company_id, company_name, street, city, state, zip_code)

                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO client (company_id, first_name, last_name, phone, email)
                            VALUES (%s, %s, %s, %s, %s);
                            """,
                            (company_id, first_name, last_name, phone, email if email else None),
                        )
                    conn.commit()

                show_toast(f"Contact added successfully! Company ID: {company_id}", "info")
                clear_fields()
                self.filtered_contacts = []
                update_contact_list()
                update_company_list()
            except Exception:
                logger.exception("Add contact failed")
                show_toast("Unable to add contact. Please try again.", "error")
                

        def update_contact():
            """
            Update an existing contact in the contact book.
            """
            _, selected_contact = get_selected_contact()
            if not selected_contact:
                show_toast("No contact selected!", "warning")
                return

            company_id_value = entry_company_id.get().strip()
            company_name = combo_company.get().strip()
            billing_address = entry_billing_address.get().strip()
            client_name = entry_client.get().strip()
            phone = entry_phone.get().strip()
            email = entry_email.get().strip()

            if not company_id_value or not company_name or not billing_address or not client_name or not phone:
                show_toast("Company ID, Company, Billing Address, Client Name, and Phone are required!", "warning")
                return

            if not company_id_value.isdigit():
                show_toast("Company ID must be a number.", "warning")
                return

            address_parts = parse_billing_address(billing_address)
            if not address_parts:
                show_toast("Billing Address must be: street, city, state, zip", "warning")
                return

            first_name, last_name = split_client_name(client_name)
            if not first_name:
                show_toast("Client Name is required.", "warning")
                return

            company_id = int(company_id_value)
            street, city, state, zip_code = address_parts

            try:
                update_or_insert_company(company_id, company_name, street, city, state, zip_code)

                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE client
                            SET company_id = %s, first_name = %s, last_name = %s, phone = %s, email = %s
                            WHERE client_id = %s;
                            """,
                            (
                                company_id,
                                first_name,
                                last_name,
                                phone,
                                email if email else None,
                                selected_contact["client_id"],
                            ),
                        )
                        updated_rows = cur.rowcount
                    conn.commit()

                if updated_rows == 0:
                    show_toast("No matching contact found to update.", "warning")
                    return

                show_toast("Contact updated successfully!", "info")
                clear_fields()
                self.filtered_contacts = []
                update_contact_list()
                update_company_list()
            except Exception:
                logger.exception("Update contact failed")
                show_toast("Unable to update contact. Please try again.", "error")


        def remove_contact():
            """
            Remove a contact from the contact book.
            """
            _, selected_contact = get_selected_contact()
            if not selected_contact:
                show_toast("No contact selected!", "warning")
                return

            try:
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM client WHERE client_id = %s;",
                            (selected_contact["client_id"],),
                        )
                        deleted_rows = cur.rowcount
                    conn.commit()

                if deleted_rows == 0:
                    show_toast("No matching contact found to remove.", "warning")
                    return

                show_toast("Contact removed successfully!", "info")
                clear_fields()
                self.filtered_contacts = []
                update_contact_list()
                update_company_list()
            except Exception:
                logger.exception("Remove contact failed")
                show_toast("Unable to remove contact. Please try again.", "error")


        def search_contact():
            """
            Search for contacts in the contact book based on the search term.
            """
            company_id_value = entry_company_id.get().strip()
            company = combo_company.get().strip()
            client = entry_client.get().strip()

            if not company_id_value and not company and not client:
                show_toast("Enter Company ID, Company Name, or Client Name to search.", "warning")
                return

            if company_id_value and not company_id_value.isdigit():
                show_toast("Company ID must be a number.", "warning")
                return

            company_id_filter = int(company_id_value) if company_id_value else None
            self.filtered_contacts = fetch_contacts_from_postgresql(company_id_filter, company, client)
            update_contact_list(self.filtered_contacts)


        def clear_results():
            """
            Clear the search results and display the complete list of contacts.

            This function clears the search results and displays the complete list 
            of contacts in the contact list.

            Parameters:
            None

            Returns:
            None
            """
            self.filtered_contacts = []
            update_contact_list()
            clear_fields()


        # Handle double-click event on contact list
        def on_item_double_click(event):
            """
            Handle the double-click event on the contact list.

            This function retrieves the selected contact from the contact list and 
            populates the Tkinter entry widgets with the contact's details.

            Parameters:
            event (Event): The event object representing the double-click event.

            Returns:
            None
            """
            _, selected_contact = get_selected_contact()
            if selected_contact:
                entry_company_id.delete(0, tk.END)
                entry_company_id.insert(0, str(selected_contact["company_id"]))
                combo_company.set(selected_contact["company"])
                entry_billing_address.delete(0, tk.END)
                entry_billing_address.insert(0, selected_contact.get("billing address", ""))
                entry_client.delete(0, tk.END)
                entry_client.insert(0, selected_contact.get("client", ""))
                entry_phone.delete(0, tk.END)
                entry_phone.insert(0, selected_contact.get("phone", ""))
                entry_email.delete(0, tk.END)
                entry_email.insert(0, selected_contact.get("email", ""))


        def update_contact_list(filtered_contacts=None):
            """
            Update the contact list display.

            Parameters:
            filtered_contacts (list, optional): A list of filtered contacts to be 
            displayed. Defaults to None.

            Returns:
            None
            """
            contacts = fetch_contacts_from_postgresql() if filtered_contacts is None else filtered_contacts
            contact_list.delete(*contact_list.get_children())
            for index, contact in enumerate(contacts):
                contact_list.insert(
                    "", "end", iid=index, values=(
                        contact.get("company_id", "N/A"),
                        contact.get("company", "N/A"), 
                        contact.get("billing address", "N/A"), 
                        contact.get("client", "N/A"), 
                        contact.get("phone", "N/A"),
                        contact.get("email", "N/A")
                        )
                    )


        def update_company_list():
            """
            Update the company list in the company combobox.

            This function updates the company list in the company combobox with 
            the unique company names from the contacts list.

            Parameters:
            None

            Returns:
            None
            """
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT company_name
                        FROM company
                        WHERE company_name IS NOT NULL AND company_name <> ''
                        ORDER BY company_name;
                        """
                    )
                    rows = cur.fetchall()

            combo_company["values"] = [row[0] for row in rows]


        def select_contact():
            """
            Select a contact from the contact list and populate the main GUI fields.

            This function retrieves the selected contact from the contact list and 
            populates the corresponding fields in the main GUI (e.g., contact name, 
            company, phone, and email). If the contact list is filtered, it uses the 
            filtered data; otherwise, it loads the complete contact data. If no 
            contact is selected, it displays a warning message.

            Parameters:
            None

            Returns:
            None
            """
            _, selected_contact = get_selected_contact()
            if selected_contact:

                # Populate the fields in the main GUI
                company_var.set(selected_contact["company"])
                billing_address_var.set(selected_contact["billing address"])
                contact_name_var.set(selected_contact["client"])
                phone_var.set(selected_contact["phone"])
                email_var.set(selected_contact["email"])

                contact_book_window.destroy()  # Close the contact book window
            else:
                # messagebox.showwarning("Selection Error", "No contact selected!")
                show_toast("No contact selected!", "warning")

        # =========================================================================== #
        # ============================ Contact Book GUI ============================= #
        # =========================================================================== #
        contact_book_window = Tk()
        contact_book_window.title("Contact Book")
        contact_book_window.config(padx=25, pady=25)

        address_suggestion_window = None
        address_suggestion_listbox = None
        address_suggestion_items = []
        autocomplete_after_id = None

        def hide_address_suggestions():
            """Hide the billing address suggestion popup window."""
            nonlocal address_suggestion_window, address_suggestion_listbox, address_suggestion_items
            if address_suggestion_window is not None and address_suggestion_window.winfo_exists():
                address_suggestion_window.destroy()
            address_suggestion_window = None
            address_suggestion_listbox = None
            address_suggestion_items = []


        def apply_selected_address(index):
            """Resolve selected place_id and insert normalized address into the entry."""
            if index < 0 or index >= len(address_suggestion_items):
                return

            selected = address_suggestion_items[index]
            normalized_address = fetch_normalized_address_by_place_id(selected.get("place_id"))

            if normalized_address:
                entry_billing_address.delete(0, tk.END)
                entry_billing_address.insert(0, normalized_address)

            hide_address_suggestions()


        def on_suggestion_click(_event=None):
            """Apply currently selected suggestion row from the popup listbox."""
            if not address_suggestion_listbox:
                return

            selected_indices = address_suggestion_listbox.curselection()
            if not selected_indices:
                return

            apply_selected_address(selected_indices[0])


        def show_address_suggestions(suggestions):
            """Show address suggestions directly under Billing Address entry."""
            nonlocal address_suggestion_window, address_suggestion_listbox, address_suggestion_items
            hide_address_suggestions()

            if not suggestions:
                return

            address_suggestion_items = suggestions
            address_suggestion_window = tk.Toplevel(contact_book_window)
            address_suggestion_window.overrideredirect(True)
            address_suggestion_window.attributes("-topmost", True)

            x_pos = entry_billing_address.winfo_rootx()
            y_pos = entry_billing_address.winfo_rooty() + entry_billing_address.winfo_height()
            width = entry_billing_address.winfo_width()
            address_suggestion_window.geometry(f"{width}x140+{x_pos}+{y_pos}")

            address_suggestion_listbox = tk.Listbox(address_suggestion_window, height=6)
            address_suggestion_listbox.pack(fill="both", expand=True)

            for item in suggestions:
                address_suggestion_listbox.insert(tk.END, item.get("description", ""))

            address_suggestion_listbox.bind("<<ListboxSelect>>", on_suggestion_click)
            address_suggestion_listbox.bind("<ButtonRelease-1>", on_suggestion_click)


        def run_address_autocomplete(query_text):
            """Query Google autocomplete for Billing Address suggestions."""
            if len(query_text.strip()) < 4:
                hide_address_suggestions()
                return

            suggestions = fetch_google_address_suggestions(query_text.strip())
            show_address_suggestions(suggestions)


        def on_billing_address_key_release(_event=None):
            """Debounce autocomplete requests while typing."""
            nonlocal autocomplete_after_id
            if autocomplete_after_id:
                contact_book_window.after_cancel(autocomplete_after_id)

            current_text = entry_billing_address.get()
            autocomplete_after_id = contact_book_window.after(
                350,
                lambda: run_address_autocomplete(current_text),
            )

        # Labels and entry fields for contact information
        Label(contact_book_window, text="Company ID (blank = auto):").grid(row=0, column=0,
                                    padx=10, pady=5, sticky="e")
        entry_company_id = Entry(contact_book_window, width=40)
        entry_company_id.grid(row=0, column=1, padx=10, pady=5)

        Label(contact_book_window, text="*Company Name:").grid(row=1, column=0,
                                                            padx=10, pady=5, sticky="e")
        combo_company = ttk.Combobox(contact_book_window, width=37)
        combo_company.grid(row=1, column=1, padx=10, pady=5)

        Label(contact_book_window, text="*Billing Address:").grid(row=2, column=0,
                                                                padx=10, pady=5, sticky="e")
        entry_billing_address = Entry(contact_book_window, width=40)
        entry_billing_address.grid(row=2, column=1, padx=10, pady=5)
        entry_billing_address.bind("<KeyRelease>", on_billing_address_key_release)
        entry_billing_address.bind("<Escape>", lambda _event: hide_address_suggestions())

        Label(contact_book_window, text="*Client Name:").grid(row=3, column=0,
                                                            padx=10, pady=5, sticky="e")
        entry_client = Entry(contact_book_window, width=40)
        entry_client.grid(row=3, column=1, padx=10, pady=5)

        Label(contact_book_window, text="*Phone Number:").grid(row=4, column=0,
                                                            padx=10, pady=5, sticky="e")
        entry_phone = Entry(contact_book_window, width=40)
        entry_phone.grid(row=4, column=1, padx=10, pady=5)

        Label(contact_book_window, text="Email:").grid(row=5, column=0,
                                                    padx=10, pady=5, sticky="e")
        entry_email = Entry(contact_book_window, width=40)
        entry_email.grid(row=5, column=1, padx=10, pady=5)

        # Buttons to add, update, and search contacts
        Button(contact_book_window, width=15, text="Add Contact", 
            command=add_contact).grid(row=0, column=2, pady=5, sticky="w")
        Button(contact_book_window, width=15, text="Update Contact", 
                command=update_contact).grid(row=1, column=2, pady=5, sticky="w")
        Button(contact_book_window, width=15, text="Remove Contact", 
                command=remove_contact).grid(row=2, column=2, pady=5, sticky="w")
        Button(contact_book_window, width=15, text="Search Contacts", 
                command=search_contact).grid(row=3, column=2, pady=5, sticky="w")
        Button(contact_book_window, width=15, text="Select Contact",
            command=select_contact).grid(row=4, column=2, pady=5, sticky="w")    
        Button(contact_book_window, width=15, text="Clear Results", 
                command=clear_results).grid(row=5, column=2, pady=5, sticky="w")


        # Create contact list display
        contact_list = ttk.Treeview(contact_book_window, 
                        columns=("Company ID", "Company Name", "Billing Address", 
                                            "Client Name", "Phone Number", 
                                            "Email"), show="headings")
        contact_list.heading("Company ID", text="Company ID")
        contact_list.heading("Company Name", text="Company Name")
        contact_list.heading("Billing Address", text="Billing Address")
        contact_list.heading("Client Name", text="Client Name")
        contact_list.heading("Phone Number", text="Phone Number")
        contact_list.heading("Email", text="Email")
        contact_list.grid(row=7, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

        # Bind double-click event to inventory list
        contact_list.bind("<Double-1>", on_item_double_click)

        # Bind the function to auto-populate billing address when a company is selected
        def on_company_selected(event):
            """
            Auto-populate the Billing Address when a company is selected from the dropdown.
            """
            selected_company = combo_company.get()
            if not selected_company:
                return

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT company_id, street, city, state, zip
                        FROM company
                        WHERE company_name = %s
                        ORDER BY company_id
                        LIMIT 1;
                        """,
                        (selected_company,),
                    )
                    row = cur.fetchone()

            if row:
                entry_company_id.delete(0, tk.END)
                entry_company_id.insert(0, str(row[0]))

                entry_billing_address.delete(0, tk.END)
                entry_billing_address.insert(0, format_billing_address(row[1], row[2], row[3], row[4]))
                hide_address_suggestions()

        # After creating combo_company:
        combo_company.bind("<<ComboboxSelected>>", on_company_selected)

        # Update contact list display on startup
        update_contact_list()
        update_company_list()

        contact_book_window.mainloop()
        

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    contact_book = ContactBook()
    contact_book.open_contact_book(
        company_var=tk.StringVar(),
        billing_address_var=tk.StringVar(),
        contact_name_var=tk.StringVar(),
        phone_var=tk.StringVar(),
        email_var=tk.StringVar()
    )
