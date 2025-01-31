import streamlit as st
from io import BytesIO, StringIO
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
import qrcode
import os
import pyodbc
import pandas as pd

# Function to generate QR code
def generate_qr_code(data):
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=15,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    return img

# Function to create PDF with QR code and dynamic text for each row
def create_pdf_with_qr_from_data(data, label_width, label_height, selected_fields, bold_fields, qr_field):
    output = BytesIO()

    # Define custom label size
    page_width = label_width
    page_height = label_height

    # Initialize canvas for single label per page
    c = canvas.Canvas(output, pagesize=(page_width, page_height))

    qr_size = 1 * cm  # QR code size
    padding = 0.07 * cm  # Padding between elements

    # Process each row in the data
    for index, row in data.iterrows():
        # Generate QR code based on selected QR field
        qr_img = generate_qr_code(row[qr_field])
        qr_img_path = f"{row[qr_field]}_temp_qr.png"
        qr_img.save(qr_img_path)

        # Place QR code on label
        qr_x = padding
        qr_y = (label_height - qr_size) / 2  # Center QR vertically
        c.drawImage(qr_img_path, qr_x, qr_y, width=qr_size, height=qr_size)

        # Remove temporary QR image
        os.remove(qr_img_path)

        # Add selected fields as text
        text_x = qr_x + qr_size + padding
        text_y = label_height - padding - 0.55 * cm  # Start below the top margin

        for idx, field in enumerate(selected_fields):
            field_value = row.get(field, "N/A")

            # Apply bold font for selected fields
            if field in bold_fields:
                c.setFont("Helvetica-Bold", 6)
                c.drawString(text_x, text_y - idx * 0.4 * cm, f"{field}: {field_value}")
            else:
                c.setFont("Helvetica", 6)
                c.drawString(text_x, text_y - idx * 0.4 * cm, f"{field}: {field_value}")

        # Start a new page for each label
        c.showPage()

    # Save the PDF
    c.save()
    output.seek(0)
    return output

# SQL Server connection function
def connect_to_sql_server():
    try:
        connection = pyodbc.connect(
            "Driver={ODBC Driver 17 for SQL Server};"
            "Server=CLS-PAE-FL71409\\SQLEXPRESS;"
            "Database=LabelDB;"
            "Trusted_Connection=yes;"
        )
        st.success("Connected to SQL Server successfully!")
        return connection
    except Exception as e:
        st.error(f"Error connecting to SQL Server: {e}")
        return None

# Function to fetch data from 'ProjectTable'
def fetch_data_from_project_table(connection):
    query = "SELECT * FROM Sample_QR"
    try:
        df = pd.read_sql(query, connection)
        return df
    except Exception as e:
        st.error(f"Error fetching data from Sample_QR: {e}")
        return None

# Streamlit app
st.title("QR Label Generator")

# Set default label dimensions (3.8 cm x 1.9 cm)
label_width = 3.8 * cm
label_height = 1.9 * cm

# Choose data source: CSV or Database
data_source = st.radio("Select data source", ["Database", "CSV"])

data = None

if data_source == "Database":
    st.header("Fetch Data from Database")
    # Connect to SQL Server
    connection = connect_to_sql_server()

    if connection:
        # Fetch and display data from the 'ProjectTable'
        data = fetch_data_from_project_table(connection)

        if data is not None:
            st.write("Data from Sample_QR:")
            st.dataframe(data)

elif data_source == "CSV":
    st.header("Upload CSV File")
    uploaded_csv = st.file_uploader("Upload CSV File", type=["csv"])

    if uploaded_csv is not None:
        try:
            csv_content = uploaded_csv.read().decode("utf-8")
            data = pd.read_csv(StringIO(csv_content))
            st.success("CSV uploaded successfully.")
            st.write("Preview of uploaded data:")
            st.dataframe(data)
        except Exception as e:
            st.error(f"An error occurred while reading the CSV file: {e}")

if data is not None:
    # Allow user to select which fields to display in the label
    fieldnames = data.columns.tolist()

    # Select a column to filter the range
    range_column = st.selectbox("Select column for filtering range", fieldnames)

    # Determine unique values in the selected column
    unique_values = sorted(data[range_column].dropna().unique())

    # Range selector (multiselect or slider depending on the type of unique_values)
    if data[range_column].dtype in ['int64', 'float64']:
        # Numeric range: Use slider
        min_val = min(unique_values)
        max_val = max(unique_values)
        selected_range = st.slider(
            "Select range", 
            min_value=min_val, 
            max_value=max_val, 
            value=(min_val, max_val)
        )
        # Filter data based on numeric range
        filtered_data = data[(data[range_column] >= selected_range[0]) & (data[range_column] <= selected_range[1])]
    else:
        # Non-numeric range: Use multiselect
        selected_range = st.multiselect(
            "Select values", unique_values, default=unique_values
        )
        # Filter data based on selected values
        filtered_data = data[data[range_column].isin(selected_range)]

    st.write("Filtered Data:")
    st.dataframe(filtered_data)

    # Allow user to specify how many labels to print
    label_count = st.number_input(
        "How many labels do you want to print?",
        min_value=1,
        max_value=len(filtered_data),
        value=len(filtered_data)
    )

    # Limit the filtered data to the specified number of labels
    if label_count < len(filtered_data):
        filtered_data = filtered_data.iloc[:label_count]

    st.write("Data for Labels:")
    st.dataframe(filtered_data)

    # Allow user to select fields to display in the label
    selected_fields = st.multiselect("Select fields to display", fieldnames, default=[])

    # Add UI for bold text selection
    bold_fields = st.multiselect("Fields to display in bold", fieldnames, default=[])

    # Allow user to select which field to generate QR code
    qr_field = st.selectbox("Select field for QR code", fieldnames)

    # Generate PDF with QR codes for the filtered data
    if st.button("Generate PDF"):
        pdf_output = create_pdf_with_qr_from_data(
            filtered_data, label_width, label_height, selected_fields, bold_fields, qr_field
        )

        # Add download button
        st.download_button(
            label="Download QR Code PDF",
            data=pdf_output,
            file_name="QR_Labels.pdf",
            mime="application/pdf"
        )
