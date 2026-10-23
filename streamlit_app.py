
import streamlit as st
import pandas as pd
import requests

from snowflake.snowpark.context import get_active_session


# ==================================================
# 1. PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Customize Your Smoothie",
    page_icon="🍓",
    layout="centered"
)

API_BASE_URL = "https://my.smoothiefroot.com/api/fruit"

st.title("🍓 Customize Your Smoothie")
st.write("Choose your favourite fruits and create your smoothie order.")


# ==================================================
# 2. SNOWFLAKE CONNECTION
# ==================================================

def get_snowflake_connection():
    return st.connection("snowflake", type="snowflake")


# ==================================================
# 3. LOAD FRUIT OPTIONS FROM SNOWFLAKE
# ==================================================

@st.cache_data(ttl=300)
def get_fruit_options():
    conn = get_snowflake_connection()

    dataframe = conn.query("""
        SELECT
            FRUIT_NAME,
            SEARCH_ON
        FROM SMOOTHIES.PUBLIC.FRUIT_OPTIONS
        ORDER BY FRUIT_NAME
    """)

    return pd.DataFrame(dataframe)


try:
    pd_df = get_fruit_options()

    required_columns = {"FRUIT_NAME", "SEARCH_ON"}

    if not required_columns.issubset(pd_df.columns):
        st.error(
            "The FRUIT_OPTIONS table must contain "
            "FRUIT_NAME and SEARCH_ON columns."
        )
        st.stop()

    # Clean the values without changing the dropdown labels.
    pd_df["FRUIT_NAME"] = (
        pd_df["FRUIT_NAME"].fillna("").astype(str).str.strip()
    )

    pd_df["SEARCH_ON"] = (
        pd_df["SEARCH_ON"].fillna("").astype(str).str.strip()
    )

    # Remove rows without a display name.
    pd_df = pd_df[pd_df["FRUIT_NAME"] != ""]

    # Create a lookup from the displayed fruit name to SEARCH_ON.
    search_on_lookup = (
        pd_df.drop_duplicates(subset=["FRUIT_NAME"])
        .set_index("FRUIT_NAME")["SEARCH_ON"]
        .to_dict()
    )

    fruit_options = pd_df["FRUIT_NAME"].drop_duplicates().tolist()


    # ==================================================
    # 4. SMOOTHIE ORDER FORM
    # ==================================================

    st.subheader("Create Your Smoothie")

    with st.form("smoothie_order_form"):

        name_on_order = st.text_input(
            "Name on smoothie order",
            placeholder="Enter your name"
        )

        fruit_chosen = st.multiselect(
            "Choose up to 5 fruits:",
            options=fruit_options,
            max_selections=5,
            key="selected_fruits"
        )

        submitted = st.form_submit_button(
            "Submit Smoothie Order",
            use_container_width=True
        )

    if submitted:

        if not name_on_order.strip():
            st.warning("Please enter a name for your order.")

        elif not fruit_chosen:
            st.warning("Please select at least one fruit.")

        else:
            try:
                session = get_active_session()

                try:
                    ingredients = ", ".join(fruit_chosen)

                    session.sql(
                        """
                        INSERT INTO SMOOTHIES.PUBLIC.ORDERS
                            (NAME_ON_ORDER, INGREDIENTS)
                        VALUES (?, ?)
                        """,
                        params=[
                            name_on_order.strip(),
                            ingredients
                        ]
                    ).collect()

                    st.success(
                        f"Thank you, {name_on_order.strip()}! "
                        "Your smoothie order has been saved."
                    )

                finally:
                    session.close()

            except Exception as e:
                st.error(
                    "Your order could not be saved. "
                    f"Please check the Snowflake connection. Details: {e}"
                )


    # ==================================================
    # 5. LOAD THE SMOOTHIEFROOT API CATALOGUE
    # ==================================================

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


    # ==================================================
    # 6. NORMALISE FRUIT NAMES
    # ==================================================

    def normalize_fruit_name(name):
        return " ".join(
            str(name).casefold().strip().split()
        )


    def compact_fruit_name(name):
        return "".join(
            character
            for character in normalize_fruit_name(name)
            if character.isalnum()
        )


    # ==================================================
    # 7. MATCH SEARCH_ON TO THE API CATALOGUE
    # ==================================================

    def find_fruit_data(
        search_value,
        fruit_lookup,
        compact_lookup
    ):
        """
        Match SEARCH_ON against the API catalogue.
        The displayed fruit name remains unchanged.
        """

        if not search_value:
            return None

        aliases = {
            "dragon fruit": "dragonfruit",
            "elderberries": "elderberry",
            "ugli fruit": "ugli fruit jamaican tangelo",
            "ximenia": "ximenia hog plum",
        }

        normalized = normalize_fruit_name(search_value)
        normalized = aliases.get(normalized, normalized)

        # First try an exact name match.
        if normalized in fruit_lookup:
            return fruit_lookup[normalized]

        # Then try matching without spaces or punctuation.
        compact_name = compact_fruit_name(normalized)

        if compact_name in compact_lookup:
            return compact_lookup[compact_name]

        # Finally, try a singular or plural variation.
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


    # ==================================================
    # 8. EXTRACT NUTRITION INFORMATION
    # ==================================================

    def find_nutrition_data(fruit_data):

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

        # Some API records store nutrition fields directly.
        possible_fields = (
            "carbohydrates",
            "carbs",
            "protein",
            "fat",
            "sugar",
            "calories",
        )

        direct_nutrition = {
            key: fruit_data[key]
            for key in possible_fields
            if key in fruit_data
        }

        return direct_nutrition or None


    # ==================================================
    # 9. DISPLAY SELECTED FRUIT INFORMATION
    # ==================================================

    st.subheader("Fruit Information")

    if fruit_chosen:

        try:
            catalogue = get_smoothiefroot_catalogue()

            # Build lookup dictionaries from API fruit names.
            fruit_lookup = {}
            compact_lookup = {}

            for item in catalogue:

                if isinstance(item, dict) and item.get("name"):

                    api_name = item["name"]

                    normalized_name = normalize_fruit_name(api_name)
                    compact_name = compact_fruit_name(api_name)

                    fruit_lookup[normalized_name] = item
                    compact_lookup[compact_name] = item

            # Process each fruit selected by the user.
            for fruit_chosen_name in fruit_chosen:

                # Retrieve the API search value from pandas.
                matching_rows = pd_df.loc[
                    pd_df["FRUIT_NAME"] == fruit_chosen_name,
                    "SEARCH_ON"
                ]

                if matching_rows.empty:
                    st.warning(
                        f"No SEARCH_ON value was found for "
                        f"{fruit_chosen_name}."
                    )
                    continue

                search_on = matching_rows.iloc[0]

                st.write(
                    f"The search value for {fruit_chosen_name} "
                    f"is {search_on}."
                )

                if not search_on:
                    st.warning(
                        f"Please populate SEARCH_ON for "
                        f"{fruit_chosen_name} in Snowflake."
                    )
                    continue

                # Find the corresponding API catalogue record.
                fruit_data = find_fruit_data(
                    search_on,
                    fruit_lookup,
                    compact_lookup
                )

                if fruit_data:

                    st.markdown(f"### {fruit_chosen_name}")

                    nutrition = find_nutrition_data(fruit_data)

                    if nutrition:
                        st.write("**Nutrition information**")
                        st.json(nutrition)

                    else:
                        st.info(
                            "The API record does not contain "
                            "recognised nutrition fields."
                        )

                    with st.expander(
                        f"View API details for {fruit_chosen_name}"
                    ):
                        st.json(fruit_data)

                else:
                    st.warning(
                        f"No API catalogue match was found for "
                        f"'{search_on}', selected as "
                        f"'{fruit_chosen_name}'. Check the "
                        "SEARCH_ON value against the API catalogue."
                    )

        except requests.RequestException as e:
            st.error(
                f"Could not retrieve fruit information: {e}"
            )

        except Exception as e:
            st.error(
                f"An error occurred while displaying fruit information: {e}"
            )


    # ==================================================
    # 10. OPTIONAL: VIEW API FRUIT CATALOGUE
    # ==================================================

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
            st.warning(
                f"Could not load the API fruit catalogue: {e}"
            )


except Exception as e:

    st.error(
        "Could not load the fruit options from Snowflake. "
        f"Details: {e}"
    )
