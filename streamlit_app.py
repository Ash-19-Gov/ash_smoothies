
import streamlit as st
import requests
import json
import re


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
# 7. RETRIEVE THE SMOOTHIEFROOT FRUIT CATALOGUE
# ==================================================
@st.cache_data(ttl=600)
def get_smoothiefroot_catalogue():
    """Retrieve fruit records from the API catalogue."""

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

    raise ValueError(
        "The API returned an unexpected fruit catalogue format."
    )


# ==================================================
# 8. NORMALISE AND MATCH FRUIT NAMES
# ==================================================
def normalize_fruit_name(name):
    """Standardise names for case-insensitive matching."""

    return " ".join(
        str(name).strip().casefold().split()
    )


def compact_fruit_name(name):
    """Remove spaces and punctuation for alternative matching."""

    return re.sub(
        r"[^a-z0-9]",
        "",
        normalize_fruit_name(name)
    )


def find_fruit_data(fruit_chosen, fruit_lookup, compact_lookup):
    """Match a selected fruit to an API catalogue record."""

    selected_name = normalize_fruit_name(fruit_chosen)

    # Explicit aliases for known differences.
    aliases = {
        "apples": "apple",
        "blueberries": "blueberry",
        "dragon fruit": "dragonfruit",
        "fig": "figs",
        "ugli fruit": "ugli fruit (jamaican tangelo)",
        "waxberry": "yangmei (waxberry)",
        "hog plum": "ximenia (hog plum)",
        "jujube": "ziziphus jujube"
    }

    candidates = [selected_name]

    if selected_name in aliases:
        candidates.append(aliases[selected_name])

    # Try basic singular/plural alternatives.
    if selected_name.endswith("ies"):
        candidates.append(selected_name[:-3] + "y")
    elif selected_name.endswith("s") and not selected_name.endswith("ss"):
        candidates.append(selected_name[:-1])

    # Match using normalised names first.
    for candidate in candidates:
        if candidate in fruit_lookup:
            return fruit_lookup[candidate]

    # Try matching names without spaces or punctuation.
    for candidate in candidates:
        compact_name = compact_fruit_name(candidate)

        if compact_name in compact_lookup:
            return compact_lookup[compact_name]

    return None


# ==================================================
# 9. FIND AND DISPLAY NUTRITION INFORMATION
# ==================================================
def find_nutrition_data(fruit_data):
    """Find nutrition information under common API field names."""

    nutrition_keys = {
        "nutrition",
        "nutritions",
        "nutritioninfo",
        "nutrition_info",
        "nutritionalinfo",
        "nutritional_info",
        "nutritioninformation",
        "nutrition_information"
    }

    def search_nested(value):
        if isinstance(value, dict):
            for key, item in value.items():
                normalised_key = compact_fruit_name(key)

                if normalised_key in {
                    compact_fruit_name(k) for k in nutrition_keys
                }:
                    if isinstance(item, (dict, list)):
                        return item

                result = search_nested(item)

                if result is not None:
                    return result

        elif isinstance(value, list):
            for item in value:
                result = search_nested(item)

                if result is not None:
                    return result

        return None

    nutrition = search_nested(fruit_data)

    if nutrition is not None:
        return nutrition

    # Some API responses provide nutrition values directly
    # rather than placing them inside a nutrition object.
    nutrition_fields = {
        "calories",
        "energy",
        "carbohydrates",
        "carbs",
        "fat",
        "protein",
        "sugar",
        "sugars",
        "fiber",
        "fibre",
        "serving_size"
    }

    direct_values = {
        key: value
        for key, value in fruit_data.items()
        if compact_fruit_name(key) in {
            compact_fruit_name(field)
            for field in nutrition_fields
        }
        and not isinstance(value, (dict, list))
    }

    if direct_values:
        return direct_values

    return None


# ==================================================
# 10. DISPLAY FRUIT INFORMATION
# ==================================================
st.divider()

st.subheader("🍓 Nutrition Information for Your Fruits")

st.write(
    "Select your fruits above and retrieve the available "
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

        try:
            with st.spinner("Retrieving fruit information..."):
                catalogue = get_smoothiefroot_catalogue()

            # Build searchable dictionaries from API records.
            fruit_lookup = {}
            compact_lookup = {}

            for item in catalogue:
                if isinstance(item, dict) and item.get("name"):
                    api_name = normalize_fruit_name(item["name"])

                    fruit_lookup[api_name] = item
                    compact_lookup[
                        compact_fruit_name(item["name"])
                    ] = item

            st.subheader("Your Fruit Information")

            for fruit_chosen in selected_fruits:

                fruit_data = find_fruit_data(
                    fruit_chosen,
                    fruit_lookup,
                    compact_lookup
                )

                st.markdown(f"### {fruit_chosen}")

                if fruit_data is None:

                    st.warning(
                        f"No matching API record was found for "
                        f"{fruit_chosen}."
                    )

                    continue

                nutrition = find_nutrition_data(fruit_data)

                if nutrition is not None:
                    st.write("**Available nutrition information**")
                    st.json(nutrition)

                else:
                    st.warning(
                        "A fruit record was found, but no recognised "
                        "nutrition field was identified. Expand the "
                        "full API record below to inspect the response."
                    )

                # Keep the complete API record available for diagnosis.
                with st.expander(
                    f"View full API record: {fruit_chosen}"
                ):
                    st.json(fruit_data)

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

        except (ValueError, TypeError) as e:

            st.error(
                f"Unable to process the API response: {e}"
            )


# ==================================================
# 11. OPTIONAL API CATALOGUE DIAGNOSTICS
# ==================================================
with st.expander("View fruit names available in the API"):

    if st.button("Load Available Fruit Names"):

        try:
            catalogue = get_smoothiefroot_catalogue()

            available_names = sorted(
                item["name"]
                for item in catalogue
                if isinstance(item, dict) and item.get("name")
            )

            st.write(available_names)

        except requests.RequestException as e:
            st.error(f"Unable to load fruit names: {e}")

        except ValueError as e:
            st.error(f"Unable to process the API response: {e}")
