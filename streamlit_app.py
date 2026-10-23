
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
# 7. RETRIEVE THE FRUIT CATALOGUE
# ==================================================
st.divider()

st.subheader("🍓 Nutrition Information for Your Fruits")

st.write(
    "Select your fruits above and retrieve their available "
    "nutrition information from the SmoothieFroot API."
)


@st.cache_data(ttl=600)
def get_smoothiefroot_catalogue():
    """Retrieve the fruit catalogue from the API."""

    response = requests.get(
        f"{API_BASE_URL}/all",
        timeout=20
    )

    response.raise_for_status()
    data = response.json()

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("fruits", "data", "results"):
            if isinstance(data.get(key), list):
                return data[key]

        if data.get("name"):
            return [data]

    raise ValueError("Unexpected fruit catalogue format.")


def normalize_fruit_name(name):
    """Standardise fruit names for matching."""

    return " ".join(
        str(name).strip().casefold().split()
    )


if st.button("Get Nutrition Data", type="primary"):

    selected_fruits = st.session_state.get(
        "selected_fruits", []
    )

    if not selected_fruits:
        st.warning("Please select at least one fruit first.")

    else:
        try:
            with st.spinner("Retrieving fruit information..."):
                catalogue = get_smoothiefroot_catalogue()

            fruit_lookup = {
                normalize_fruit_name(item["name"]): item
                for item in catalogue
                if isinstance(item, dict) and item.get("name")
            }

            st.subheader("Your Fruit Information")

            for fruit_chosen in selected_fruits:

                fruit_data = fruit_lookup.get(
                    normalize_fruit_name(fruit_chosen)
                )

                if fruit_data is not None:
                    st.markdown(f"**{fruit_chosen}**")
                    st.json(fruit_data)

                else:
                    st.warning(
                        f"No matching API record was found for "
                        f"{fruit_chosen}."
                    )

            with st.expander("View fruit names available in the API"):
                available_names = sorted(
                    item["name"]
                    for item in catalogue
                    if isinstance(item, dict) and item.get("name")
                )

                st.write(available_names)

        except requests.RequestException as e:
            st.error(f"Unable to retrieve the fruit catalogue: {e}")

        except ValueError as e:
            st.error(f"Unable to process the API response: {e}")

