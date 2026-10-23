
# Import Python packages
import streamlit as st
from snowflake.snowpark.functions import col

# Configure the app
st.set_page_config(
    page_title="Customize Your Smoothie",
    page_icon="🥤"
)

# Display the app title and introduction
st.title(":cup_with_straw: Customize Your Smoothie! :cup_with_straw:")
st.write("Create your own smoothie by selecting your favourite ingredients.")

# Connect to Snowflake from Streamlit Cloud
try:
    conn = st.connection("snowflake", type="snowflake")
    session = conn.session()

    # Retrieve available fruit names from Snowflake
    fruit_names = (
        session.table("SMOOTHIES.PUBLIC.FRUIT_OPTIONS")
        .select(col("FRUIT_NAME"))
        .sort(col("FRUIT_NAME"))
    )

    fruit_list = [
        row["FRUIT_NAME"]
        for row in fruit_names.collect()
    ]

except Exception:
    st.error(
        "Unable to connect to Snowflake or retrieve the fruit options. "
        "Please check your Snowflake connection settings and permissions."
    )
    st.stop()

# Create the smoothie order form
with st.form("smoothie_order_form"):

    # Get the customer's name
    name_on_order = st.text_input("Name on smoothie order")

    # Allow customers to select a maximum of 5 ingredients
    ingredients_list = st.multiselect(
        "Choose up to 5 ingredients:",
        options=fruit_list,
        max_selections=5
    )

    # Submit button
    submit_order = st.form_submit_button("Submit Order")

# Process the order only when the form is submitted
if submit_order:

    # Validate the customer's input
    if not name_on_order.strip():
        st.warning("Please enter your name.")

    elif not ingredients_list:
        st.warning("Please select at least one ingredient.")

    else:
        # Separate ingredients with commas
        ingredients_string = ", ".join(ingredients_list)

        try:
            # Insert the order using parameterized SQL
            insert_statement = """
                INSERT INTO SMOOTHIES.PUBLIC.ORDERS
                    (NAME_ON_ORDER, INGREDIENTS)
                VALUES (?, ?)
            """

            session.sql(
                insert_statement,
                params=[
                    name_on_order.strip(),
                    ingredients_string
                ]
            ).collect()

            # Confirm successful submission
            st.success(
                f"Your smoothie is ordered, {name_on_order.strip()}!",
                icon="✅"
            )

            st.write("**Your ingredients:**", ingredients_string)

        except Exception:
            st.error(
                "Your order could not be saved. "
                "Please check the Snowflake connection and table permissions."
            )

