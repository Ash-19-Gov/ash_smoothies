
import streamlit as st
import requests


# ==================================================
# 1. CONFIGURE THE STREAMLIT APP
# ==================================================
st.set_page_config(
    page_title="Customize Your Smoothie",
    page_icon="🥤",
    layout="wide"
)

API_BASE_URL = "https://my.smoothiefroot.com/api/fruit"


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
# 4. RETRIEVE FRUIT OPTIONS FROM SNOWFLAKE
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
        conn.reset()
        fruit_df = conn.query(query, ttl=0)

    return (
        fruit_df["FRUIT_NAME"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda values: values != ""]
        .tolist()
    )


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
        max_selections=5,
        key="selected_fruits"
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
        session = None

        try:
            conn = get_snowflake_connection()
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
            st.error("Your smoothie order could not be saved.")
            st.exception(e)

        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass


# ==================================================
# 7. RETRIEVE NUTRITION DATA USING fruit_chosen
# ==================================================
st.divider()

st.subheader("🍓 Nutrition Information for Your Fruits")

st.write(
    "Select your fruits above and retrieve their available "
    "information from the SmoothieFroot API."
)

if st.button("Get Nutrition Data", type="primary"):

    selected_fruits = st.session_state.get(
        "selected_fruits", []
    )

    if not selected_fruits:

        st.warning(
            "Please select at least one fruit in the "
            "Build Your Smoothie section first."
        )

    else:

        st.write("### Your Fruit Information")

        for fruit_chosen in selected_fruits:

            # Prepare the selected fruit for the API URL.
            fruit_name = (
                fruit_chosen.strip()
                .lower()
                .replace(" ", "-")
            )

            # Build the API URL using fruit_chosen.
            api_url = f"{API_BASE_URL}/{fruit_name}"

            try:
                with st.spinner(
                    f"Retrieving information for {fruit_chosen}..."
                ):

                    response = requests.get(
                        api_url,
                        timeout=20
                    )

                    response.raise_for_status()
                    fruit_data = response.json()

                st.subheader(fruit_chosen)

                # Display the information returned by the API.
                if isinstance(fruit_data, dict):

                    nutrition = fruit_data.get("nutritions")

                    if isinstance(nutrition, dict):
                        st.write("**Nutrition information**")
                        st.json(nutrition)

                    st.write("**Full API response**")
                    st.json(fruit_data)

                else:
                    st.json(fruit_data)

            except requests.Timeout:

                st.warning(
                    f"The API timed out while retrieving "
                    f"{fruit_chosen}. Please try again."
                )

            except requests.HTTPError as e:

                st.warning(
                    f"The API could not find information for "
                    f"{fruit_chosen}. Details: {e}"
                )

            except requests.RequestException as e:

                st.error(
                    f"Unable to connect to the API for "
                    f"{fruit_chosen}: {e}"
                )

            except ValueError:

                st.warning(
                    f"The API returned an invalid response "
                    f"for {fruit_chosen}."
                )
