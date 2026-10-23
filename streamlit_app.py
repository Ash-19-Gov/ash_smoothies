
import streamlit as st
import requests
import pandas as pd
from snowflake.snowpark.functions import col

# Configure the app
st.set_page_config(
    page_title="Customize Your Smoothie",
    page_icon="🥤"
)

# Display the app heading
st.title("🥤 Customize Your Smoothie! 🥤")
st.write(
    "Create your own smoothie by selecting your favourite ingredients."
)

# Connect to Snowflake
try:
    conn = st.connection("snowflake", type="snowflake")
    session = conn.session()

    # Retrieve available fruits from Snowflake
    fruit_rows = (
        session.table("SMOOTHIES.PUBLIC.FRUIT_OPTIONS")
        .select(col("FRUIT_NAME"))
        .sort(col("FRUIT_NAME"))
        .collect()
    )

    fruit_list = [row["FRUIT_NAME"] for row in fruit_rows]

except Exception as e:
    st.error("Unable to connect to Snowflake or retrieve fruit options.")
    st.exception(e)
    st.stop()

# Smoothie order form
st.subheader("Build Your Smoothie")

with st.form("smoothie_order_form"):
    name_on_order = st.text_input("Name on smoothie order")

    ingredients_list = st.multiselect(
        "Choose up to 5 ingredients:",
        options=fruit_list,
        max_selections=5
    )

    submit_order = st.form_submit_button("Submit Order")

if submit_order:
    if not name_on_order.strip():
        st.warning("Please enter your name.")
    elif not ingredients_list:
        st.warning("Please select at least one ingredient.")
    else:
        ingredients_string = ", ".join(ingredients_list)

        try:
            session.sql(
                """
                INSERT INTO SMOOTHIES.PUBLIC.ORDERS
                    (NAME_ON_ORDER, INGREDIENTS)
                VALUES (?, ?)
                """,
                params=[
                    name_on_order.strip(),
                    ingredients_string
                ]
            ).collect()

            st.success(
                f"Your smoothie is ordered, {name_on_order.strip()}!"
            )
            st.write("**Your ingredients:**", ingredients_string)

        except Exception as e:
            st.error("Your order could not be saved.")
            st.caption(f"Technical details: {e}")

# SmoothieFroot API example from the training lesson
st.divider()
st.subheader("SmoothieFroot API Example")

if st.button("Get Watermelon Data"):
    try:
        response = requests.get(
            "https://my.smoothiefroot.com/api/fruit/watermelon",
            timeout=15
        )

        if response.status_code == 200:
            smoothiefroot_data = response.json()

            st.write("API response:")
            st.json(smoothiefroot_data)

            # Convert the returned JSON to a DataFrame
            if isinstance(smoothiefroot_data, list):
                sf_df = pd.DataFrame(smoothiefroot_data)
            elif isinstance(smoothiefroot_data, dict):
                sf_df = pd.DataFrame([smoothiefroot_data])
            else:
                sf_df = pd.DataFrame(
                    {"response": [str(smoothiefroot_data)]}
                )

            st.write("SmoothieFroot DataFrame:")
            st.dataframe(sf_df, use_container_width=True)

        else:
            st.error(
                f"API request failed with status code "
                f"{response.status_code}."
            )

    except requests.RequestException as e:
        st.error(f"Unable to reach the SmoothieFroot API: {e}")

    except ValueError:
        st.error("The API response was not valid JSON.")
