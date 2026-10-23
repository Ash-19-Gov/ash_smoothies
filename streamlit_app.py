
# Import Python packages
import streamlit as st
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import col

# Get the active Snowflake session
session = get_active_session()

# Display the app title and introduction
st.title(":cup_with_straw: Customize Your Smoothie! :cup_with_straw:")
st.write("Create your own smoothie by selecting your favourite ingredients.")

# Get the customer's name
name_on_order = st.text_input("Name on smoothie order")

# Retrieve available fruit names from Snowflake
fruit_names = (
    session.table("SMOOTHIES.PUBLIC.FRUIT_OPTIONS")
    .select(col("FRUIT_NAME"))
)

# Convert fruit names into a Python list
fruit_list = [
    row["FRUIT_NAME"]
    for row in fruit_names.collect()
]

# Allow customers to select a maximum of 5 ingredients
ingredients_list = st.multiselect(
    "Choose up to 5 ingredients:",
    options=fruit_list,
    max_selections=5
)

# Display results only when ingredients have been selected
if ingredients_list:

    # Create an empty string
    ingredients_string = ""

    # Convert the selected ingredients into a string
    for fruit_chosen in ingredients_list:
        ingredients_string += fruit_chosen

    # Display the selected ingredients
    st.write(ingredients_string)

    # Build the SQL INSERT statement
    my_insert_stmt = """INSERT INTO SMOOTHIES.PUBLIC.ORDERS
        (NAME_ON_ORDER, INGREDIENTS)
        VALUES ('""" + name_on_order + """', '""" + ingredients_string + """')"""

    # Display the SQL statement
    st.write(my_insert_stmt)

    # Add a Submit button
    submit_order = st.button("Submit Order")

    # Insert the order into Snowflake only when submitted
    if submit_order:
        session.sql(my_insert_stmt).collect()
        st.success(
            "Your smoothie is ordered, " + name_on_order + "!",
            icon="✅"
        )
