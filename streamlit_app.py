
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
    """Get the Streamlit-managed Snowflake connection."""
    return st.connection("snowflake", type="snowflake")


# ==================================================
# 4. RETRIEVE FRUIT OPTIONS
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
        # Reinitialise a stale connection and retry the read.
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
# 7. SMOOTHIEFROOT NUTRITION DATA FOR SELECTED FRUITS
# ==================================================
st.divider()
st.subheader("🍓 Nutrition Information for Your Fruits")

if st.button("Get Nutrition Data", type="primary"):

    if not ingredients_list:
        st.warning("Please select at least one fruit first.")

    else:
        nutrition_results = []

        for fruit in ingredients_list:
            # Convert the selected fruit into an API URL slug.
            fruit_slug = fruit.strip().lower().replace(" ", "-")

            api_url = (
                f"https://my.smoothiefroot.com/api/fruit/{fruit_slug}"
            )

            try:
                with st.spinner(f"Retrieving data for {fruit}..."):
                    response = requests.get(
                        api_url,
                        timeout=15
                    )

                response.raise_for_status()
                fruit_data = response.json()

                # Add the fruit name to the displayed data.
                if isinstance(fruit_data, dict):
                    fruit_data["selected_fruit"] = fruit
                    nutrition_results.append(fruit_data)

                elif isinstance(fruit_data, list):
                    for item in fruit_data:
                        if isinstance(item, dict):
                            item["selected_fruit"] = fruit
                            nutrition_results.append(item)

            except requests.RequestException as e:
                st.warning(f"Could not retrieve data for {fruit}: {e}")

            except ValueError:
                st.warning(f"The API returned invalid JSON for {fruit}.")

        # Display the retrieved nutrition information.
        if nutrition_results:
            nutrition_df = pd.json_normalize(nutrition_results)

            st.success("Fruit information retrieved successfully!")

            st.dataframe(
                nutrition_df,
                width="stretch",
                hide_index=True
            )
        else:
            st.info(
                "No fruit data was returned. "
                "Check the selected fruit names and API response."
            )
