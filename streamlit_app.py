
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
    """Get the Streamlit-managed Snowflake connection."""
    return st.connection("snowflake", type="snowflake")


# ==================================================
# 4. RETRIEVE FRUIT OPTIONS FROM SNOWFLAKE
# ==================================================
@st.cache_data(ttl=300)
def get_fruit_options():
    """Retrieve fruit options from Snowflake."""
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
# 5. SMOOTHIE ORDER FORM
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
# 6. SAVE ORDER TO SNOWFLAKE
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
# 7. RETRIEVE THE SMOOTHIEFROOT FRUIT CATALOGUE
# ==================================================
@st.cache_data(ttl=600)
def get_smoothiefroot_catalogue():
    """Retrieve the available fruit records from the API."""
    response = requests.get(
        f"{API_BASE_URL}/all",
        timeout=20
    )

    response.raise_for_status()
    data = response.json()

    # Support either a list or a dictionary containing a fruit list.
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("fruits", "data", "results"):
            if isinstance(data.get(key), list):
                return data[key]

        # Some APIs return a single fruit as a dictionary.
        if data.get("name"):
            return [data]

    raise ValueError(
        "The fruit catalogue returned an unexpected data format."
    )


# ==================================================
# 8. MATCH SELECTED FRUITS TO NUTRITION DATA
# ==================================================
def normalize_fruit_name(name):
    """Normalise names for matching without changing displayed names."""
    return " ".join(str(name).strip().casefold().split())


def get_selected_fruit_data(selected_fruits, catalogue):
    """Match selected ingredients to fruit records in the catalogue."""
    lookup = {}

    for item in catalogue:
        if isinstance(item, dict) and item.get("name"):
            key = normalize_fruit_name(item["name"])
            lookup[key] = item

    results = []
    unmatched = []

    for selected_fruit in selected_fruits:
        selected_key = normalize_fruit_name(selected_fruit)

        # First try an exact name match.
        fruit_data = lookup.get(selected_key)

        # Try singular/plural variants only if needed.
        if fruit_data is None:
            if selected_key.endswith("ies"):
                alternative = selected_key[:-3] + "y"
            elif selected_key.endswith("s") and not selected_key.endswith("ss"):
                alternative = selected_key[:-1]
            else:
                alternative = selected_key

            fruit_data = lookup.get(alternative)

        if fruit_data is not None:
            results.append({
                "Selected Fruit": selected_fruit,
                **fruit_data
            })
        else:
            unmatched.append(selected_fruit)

    return results, unmatched


# ==================================================
# 9. DISPLAY NUTRITION DATA FOR SELECTED FRUITS
# ==================================================
st.divider()
st.subheader("🍓 Nutrition Information for Your Fruits")

st.write(
    "Select your ingredients above, then retrieve their "
    "available SmoothieFroot nutrition information."
)

if st.button("Get Nutrition Data", type="primary"):

    if not ingredients_list:
        st.warning("Please select at least one fruit first.")

    else:
        try:
            with st.spinner("Retrieving the fruit catalogue..."):
                catalogue = get_smoothiefroot_catalogue()

            nutrition_results, unmatched_fruits = (
                get_selected_fruit_data(
                    ingredients_list,
                    catalogue
                )
            )

            if nutrition_results:
                nutrition_df = pd.json_normalize(
                    nutrition_results,
                    sep="."
                )

                st.success(
                    "Nutrition data retrieved for "
                    f"{len(nutrition_results)} selected fruit(s)."
                )

                st.dataframe(
                    nutrition_df,
                    width="stretch",
                    hide_index=True
                )

            if unmatched_fruits:
                st.warning(
                    "No matching API record was found for: "
                    + ", ".join(unmatched_fruits)
                )

                st.caption(
                    "The selected name may differ from the API's "
                    "catalogue name, or the fruit may not be supported."
                )

            if not nutrition_results and not unmatched_fruits:
                st.info("No nutrition records were returned.")

        except requests.Timeout:
            st.error(
                "The SmoothieFroot API timed out. Please try again."
            )

        except requests.HTTPError as e:
            st.error(
                f"The SmoothieFroot API returned an HTTP error: {e}"
            )

        except requests.RequestException as e:
            st.error(
                f"Unable to connect to the SmoothieFroot API: {e}"
            )

        except ValueError as e:
            st.error(f"Unable to process the fruit data: {e}")
