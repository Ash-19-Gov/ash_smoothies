
import streamlit as st
import pandas as pd
import requests
from snowflake.snowpark.context import get_active_session

# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(page_title="Smoothie Order App", page_icon="🍓")

API_BASE_URL = "https://my.smoothiefroot.com/api/fruit"

st.title("🍓 Customize Your Smoothie")

# --------------------------------------------------
# SNOWFLAKE CONNECTION
# --------------------------------------------------
def get_snowflake_connection():
    return st.connection("snowflake", type="snowflake")


# --------------------------------------------------
# LOAD FRUIT OPTIONS INCLUDING SEARCH_ON
# --------------------------------------------------
@st.cache_data
def get_fruit_options():
    conn = get_snowflake_connection()

    return conn.query("""
        SELECT FRUIT_NAME, SEARCH_ON
        FROM SMOOTHIES.PUBLIC.FRUIT_OPTIONS
        ORDER BY FRUIT_NAME
    """)


try:
    my_dataframe = get_fruit_options()
    pd_df = pd.DataFrame(my_dataframe)

    # Ensure both required columns exist
    required_columns = {"FRUIT_NAME", "SEARCH_ON"}

    if not required_columns.issubset(pd_df.columns):
        st.error("The FRUIT_OPTIONS table must contain FRUIT_NAME and SEARCH_ON.")
        st.stop()

    # Clean column values
    pd_df["FRUIT_NAME"] = pd_df["FRUIT_NAME"].astype(str).str.strip()
    pd_df["SEARCH_ON"] = pd_df["SEARCH_ON"].fillna("").astype(str).str.strip()

    # --------------------------------------------------
    # SMOOTHIE ORDER FORM
    # --------------------------------------------------
    with st.form("smoothie_order_form"):
        name_on_order = st.text_input("Name on smoothie order")

        fruit_options = pd_df["FRUIT_NAME"].tolist()

        fruit_chosen = st.multiselect(
            "Choose up to 5 fruits for your smoothie:",
            options=fruit_options,
            max_selections=5,
            key="selected_fruits"
        )

        submitted = st.form_submit_button("Submit Smoothie Order")

    if submitted:
        if not name_on_order.strip():
            st.warning("Please enter a name for your order.")
        elif not fruit_chosen:
            st.warning("Please select at least one fruit.")
        else:
            try:
                # Save order using Snowpark
                session = get_active_session()

                try:
                    ingredients = ", ".join(fruit_chosen)

                    session.sql(
                        """
                        INSERT INTO SMOOTHIES.PUBLIC.ORDERS
                            (NAME_ON_ORDER, INGREDIENTS)
                        VALUES (?, ?)
                        """,
                        params=[name_on_order.strip(), ingredients]
                    ).collect()

                    st.success(
                        f"Thank you, {name_on_order.strip()}! "
                        "Your smoothie order has been saved."
                    )

                finally:
                    session.close()

            except Exception as e:
                st.error(f"Could not save your order: {e}")

    # --------------------------------------------------
    # SMOOTHIEFROOT API CATALOGUE
    # --------------------------------------------------
    @st.cache_data(ttl=3600)
    def get_smoothiefroot_catalogue():
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

        return []

    def normalize_fruit_name(name):
        return " ".join(str(name).casefold().strip().split())

    def compact_fruit_name(name):
        return "".join(
            character
            for character in normalize_fruit_name(name)
            if character.isalnum()
        )

    def find_fruit_data(search_value, fruit_lookup, compact_lookup):
        """Match SEARCH_ON against the API catalogue."""
        if not search_value:
            return None

        normalized = normalize_fruit_name(search_value)
        compact = compact_fruit_name(search_value)

        # Exact name match
        if normalized in fruit_lookup:
            return fruit_lookup[normalized]

        if compact in compact_lookup:
            return compact_lookup[compact]

        # Try a singular/plural variation
        alternatives = []

        if normalized.endswith("ies"):
            alternatives.append(normalized[:-3] + "y")
        elif normalized.endswith("s"):
            alternatives.append(normalized[:-1])
        else:
            alternatives.append(normalized + "s")

        for alternative in alternatives:
            if alternative in fruit_lookup:
                return fruit_lookup[alternative]

            alternative_compact = compact_fruit_name(alternative)

            if alternative_compact in compact_lookup:
                return compact_lookup[alternative_compact]

        return None

    def find_nutrition_data(fruit_data):
        """Find nutrition information in common API response formats."""
        if not isinstance(fruit_data, dict):
            return None

        possible_keys = (
            "nutrition",
            "nutritions",
            "nutritional_info",
            "nutrition_info",
            "nutritional_values",
        )

        for key in possible_keys:
            value = fruit_data.get(key)

            if isinstance(value, dict):
                return value

        # Some API records provide nutrition fields directly.
        nutrition_fields = (
            "carbohydrates",
            "carbs",
            "protein",
            "fat",
            "sugar",
            "calories",
        )

        direct_nutrition = {
            key: fruit_data[key]
            for key in nutrition_fields
            if key in fruit_data
        }

        return direct_nutrition or None

    # --------------------------------------------------
    # DISPLAY SEARCH_ON VALUES AND FRUIT INFORMATION
    # --------------------------------------------------
    st.subheader("Fruit Information")

    if fruit_chosen:
        try:
            catalogue = get_smoothiefroot_catalogue()

            fruit_lookup = {}
            compact_lookup = {}

            for item in catalogue:
                if isinstance(item, dict) and item.get("name"):
                    api_name = item["name"]

                    fruit_lookup[normalize_fruit_name(api_name)] = item
                    compact_lookup[compact_fruit_name(api_name)] = item

            for fruit in fruit_chosen:
                matching_rows = pd_df.loc[
                    pd_df["FRUIT_NAME"] == fruit,
                    "SEARCH_ON"
                ]

                if matching_rows.empty:
                    st.warning(f"No SEARCH_ON value found for {fruit}.")
                    continue

                search_on = matching_rows.iloc[0]

                st.write(
                    f"The search value for {fruit} is {search_on}."
                )

                fruit_data = find_fruit_data(
                    search_on,
                    fruit_lookup,
                    compact_lookup
                )

                if fruit_data:
                    st.markdown(f"### {fruit}")

                    nutrition = find_nutrition_data(fruit_data)

                    if nutrition:
                        st.write("**Nutrition information**")
                        st.json(nutrition)
                    else:
                        st.info(
                            "No separate nutrition fields were recognised "
                            "in the API response."
                        )

                    with st.expander(f"View API details for {fruit}"):
                        st.json(fruit_data)

                else:
                    st.warning(
                        f"No API catalogue match was found for "
                        f"'{search_on}' (selected as {fruit}). "
                        "Check the SEARCH_ON value in Snowflake."
                    )

        except requests.RequestException as e:
            st.error(f"Could not retrieve fruit information: {e}")

        except Exception as e:
            st.error(f"An error occurred: {e}")

    # --------------------------------------------------
    # OPTIONAL: VIEW AVAILABLE API FRUITS
    # --------------------------------------------------
    with st.expander("View available SmoothieFroot API fruits"):
        try:
            catalogue = get_smoothiefroot_catalogue()
            api_fruit_names = sorted(
                item["name"]
                for item in catalogue
                if isinstance(item, dict) and item.get("name")
            )

            st.write(api_fruit_names)

        except requests.RequestException as e:
            st.warning(f"Could not load the API fruit list: {e}")

except Exception as e:
    st.error(f"Could not load fruit options from Snowflake: {e}")
