
import streamlit as st
import requests
import pandas as pd
from snowflake.snowpark.functions import col


# ==================================================
# 1. CONFIGURE THE STREAMLIT APP
# ==================================================
st.set_page_config(
    page_title="Customize Your Smoothie",
    page_icon="🥤",
    layout="wide"
)


# ==================================================
# 2. DISPLAY THE APP HEADING
# ==================================================
st.title("🥤 Customize Your Smoothie!")
st.write(
    "Create your own smoothie by selecting your favourite ingredients."
)


# ==================================================
# 3. RETRIEVE FRUIT OPTIONS FROM SNOWFLAKE
# ==================================================
@st.cache_data(ttl=300)
def get_fruit_options():
    """Retrieve fruit options from the Snowflake table."""
    conn = st.connection("snowflake", type="snowflake")
    session = conn.session()

    try:
        fruit_rows = (
            session.table("SMOOTHIES.PUBLIC.FRUIT_OPTIONS")
            .select(col("FRUIT_NAME"))
            .sort(col("FRUIT_NAME"))
            .collect()
        )

        return [row["FRUIT_NAME"] for row in fruit_rows]

    finally:
        session.close()


try:
    fruit_list = get_fruit_options()

    if not fruit_list:
        st.warning("No fruit options were found in Snowflake.")
        st.stop()

except Exception as e:
    st.error("Unable to retrieve fruit options from Snowflake.")
    st.exception(e)
    st.stop()


# ==================================================
# 4. BUILD AND SUBMIT THE SMOOTHIE ORDER
# ==================================================
st.subheader("Build Your Smoothie")

with st.form("smoothie_order_form"):
    name_on_order = st.text_input(
        "Name on smoothie order",
        placeholder="Enter your name"
    )

    ingredients_list = st.multiselect(
        "Choose up to 5 ingredients:",
        options=fruit_list,
        max_selections=5
    )

    submit_order = st.form_submit_button(
        "Submit Order",
        type="primary"
    )


if submit_order:
    customer_name = name_on_order.strip()

    if not customer_name:
        st.warning("Please enter your name.")

    elif not ingredients_list:
        st.warning("Please select at least one ingredient.")

    else:
        ingredients_string = ", ".join(ingredients_list)
        session = None

        try:
            conn = st.connection(
                "snowflake",
                type="snowflake"
            )
            session = conn.session()

            session.sql(
                """
                INSERT INTO SMOOTHIES.PUBLIC.ORDERS
                    (NAME_ON_ORDER, INGREDIENTS)
                VALUES (?, ?)
                """,
                params=[
                    customer_name,
                    ingredients_string
                ]
            ).collect()

            st.success(
                f"Your smoothie is ordered, {customer_name}!"
            )
            st.write(
                "**Your ingredients:**",
                ingredients_string
            )

        except Exception as e:
            st.error("Your order could not be saved.")
            st.exception(e)

        finally:
            if session is not None:
                session.close()


# ==================================================
# 5. SMOOTHIEFROOT WATERMELON API
# ==================================================
st.divider()
st.subheader("🍉 SmoothieFroot API Example")

if st.button("Get Watermelon Data", type="primary"):
    api_url = (
        "https://my.smoothiefroot.com/api/fruit/watermelon"
    )

    try:
        with st.spinner("Retrieving Watermelon data..."):
            response = requests.get(
                api_url,
                timeout=15
            )

        response.raise_for_status()
        smoothiefroot_data = response.json()

        st.success("Watermelon data retrieved successfully!")

        # Display the original JSON response
        with st.expander("View API Response (JSON)"):
            st.json(smoothiefroot_data)

        # Convert JSON into a readable DataFrame
        if isinstance(smoothiefroot_data, (dict, list)):
            sf_df = pd.json_normalize(smoothiefroot_data)
        else:
            sf_df = pd.DataFrame(
                {"response": [str(smoothiefroot_data)]}
            )

        st.write("### SmoothieFroot DataFrame")

        st.dataframe(
            sf_df,
            width="stretch",
            hide_index=True
        )

    except requests.Timeout:
        st.error(
            "The API request timed out. Please try again."
        )

    except requests.HTTPError as e:
        st.error(f"The API returned an HTTP error: {e}")

    except requests.RequestException as e:
        st.error(
            f"Unable to reach the SmoothieFroot API: {e}"
        )

    except ValueError:
        st.error(
            "The API response could not be converted to valid JSON."
        )
