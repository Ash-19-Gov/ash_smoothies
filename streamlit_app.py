
import streamlit as st
import requests
import pandas as pd


# ==================================================
# 1. CONFIGURE THE STREAMLIT APP
# ==================================================
st.set_page_config(
    page_title="Customize Your Smoothie",
    page_icon="🥤",
    layout="wide"
)


# ==================================================
# 2. APP HEADING
# ==================================================
st.title("🥤 Customize Your Smoothie!")
st.write(
    "Create your own smoothie by selecting your favourite ingredients."
)


# ==================================================
# 3. SNOWFLAKE CONNECTION
# ==================================================
def get_snowflake_connection():
    """Return the Streamlit-managed Snowflake connection."""
    return st.connection("snowflake", type="snowflake")


# ==================================================
# 4. RETRIEVE FRUIT OPTIONS
# ==================================================
@st.cache_data(ttl=300)
def get_fruit_options():
    """Retrieve available fruit options from Snowflake."""
    conn = get_snowflake_connection()

    query = """
        SELECT FRUIT_NAME
        FROM SMOOTHIES.PUBLIC.FRUIT_OPTIONS
        ORDER BY FRUIT_NAME
    """

    try:
        fruit_df = conn.query(query, ttl=0)

    except Exception:
        # Reset a potentially stale connection and retry once.
        conn.reset()
        fruit_df = conn.query(query, ttl=0)

    return (
        fruit_df["FRUIT_NAME"]
        .dropna()
        .astype(str)
        .tolist()
    )


try:
    fruit_list = get_fruit_options()

    if not fruit_list:
        st.warning(
            "No fruit options were found in Snowflake. "
            "Please check the FRUIT_OPTIONS table."
        )
        st.stop()

except Exception as e:
    st.error("Unable to retrieve fruit options from Snowflake.")
    st.exception(e)
    st.stop()


# ==================================================
# 5. BUILD THE SMOOTHIE ORDER FORM
# ==================================================
st.subheader("Build Your Smoothie")

with st.form("smoothie_order_form"):
    customer_name = st.text_input(
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


# ==================================================
# 6. SAVE THE SMOOTHIE ORDER TO SNOWFLAKE
# ==================================================
if submit_order:
    customer_name = customer_name.strip()

    if not customer_name:
        st.warning("Please enter your name.")

    elif not ingredients_list:
        st.warning("Please select at least one ingredient.")

    else:
        ingredients_string = ", ".join(ingredients_list)
        order_saved = False

        try:
            conn = get_snowflake_connection()

            insert_query = """
                INSERT INTO SMOOTHIES.PUBLIC.ORDERS
                    (NAME_ON_ORDER, INGREDIENTS)
                VALUES (?, ?)
            """

            # Retry once if the first attempt encounters a connection error.
            try:
                conn.query(
                    insert_query,
                    params=[
                        customer_name,
                        ingredients_string
                    ],
                    ttl=0
                )

            except Exception:
                conn.reset()

                conn.query(
                    insert_query,
                    params=[
                        customer_name,
                        ingredients_string
                    ],
                    ttl=0
                )

            order_saved = True

        except Exception as e:
            st.error("Your smoothie order could not be saved.")
            st.exception(e)

        if order_saved:
            st.success(
                f"Your smoothie is ordered, {customer_name}!"
            )
            st.write("**Your ingredients:**", ingredients_string)


# ==================================================
# 7. WATERMELON API INTEGRATION
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
        api_data = response.json()

        st.success("Watermelon data retrieved successfully!")

        # Display the original API response.
        with st.expander("View API Response (JSON)"):
            st.json(api_data)

        # Convert the API response to a DataFrame.
        if isinstance(api_data, (dict, list)):
            api_df = pd.json_normalize(api_data)
        else:
            api_df = pd.DataFrame(
                {"response": [str(api_data)]}
            )

        st.write("### SmoothieFroot DataFrame")

        st.dataframe(
            api_df,
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
            "The API response was not valid JSON."
        )
