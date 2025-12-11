# --------------------------------------------
# 7_Review_Page.py
# --------------------------------------------
import os
import sys
import streamlit as st
import requests

# -------------------------------------------------------------------
# Ensure the project root is in sys.path
# -------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from frontend.park_data import get_parks, get_park_detail

# -------------------------------------------------------------------
# User authentication check
# -------------------------------------------------------------------
if not st.session_state.get("authenticated", False):
    st.warning("Please log in from the main page.")
    st.stop()

# -------------------------------------------------------------------
# API Base URL
# -------------------------------------------------------------------
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")

# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------

def get_session_id():
    """Get session_id from user session state"""
    user = st.session_state.get("user")
    if not user or "session_id" not in user:
        st.error("No user session found. Please log in again.")
        st.stop()
    return str(user["session_id"])

def get_park_detail(park_id):
    """Fetch park details"""
    try:
        session_id = get_session_id()
        response = requests.get(
            f"{API_BASE}/api/parks/{park_id}",
            cookies={"session_id": session_id},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Error fetching park details: {str(e)}")
        return None

def get_user_park_reviews():
    """Fetch park reviews by the current user"""
    try:
        session_id = get_session_id()
        response = requests.get(
            f"{API_BASE}/api/parks/reviews",
            cookies={"session_id": session_id},
            timeout=5
        )
        if response.status_code == 200:
            return response.json().get("reviews", [])
        return []
    except Exception as e:
        st.error(f"Error fetching park reviews: {str(e)}")
        return []

def get_user_trail_reviews():
    """Fetch trail reviews by the current user"""
    try:
        session_id = get_session_id()
        response = requests.get(
            f"{API_BASE}/api/trails/reviews",
            cookies={"session_id": session_id},
            timeout=5
        )
        if response.status_code == 200:
            return response.json().get("reviews", [])
        return []
    except Exception as e:
        st.error(f"Error fetching trail reviews: {str(e)}")
        return []

def submit_park_review(park_id, rating, comment):
    """Submit a new park review"""
    try:
        session_id = get_session_id()
        data = {
            "rating": rating,
            "review_text": comment
        }
        response = requests.post(
            f"{API_BASE}/api/parks/{park_id}/reviews",
            json=data,
            cookies={"session_id": session_id},
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            return True, response.json()
        else:
            error_msg = response.json().get("error", response.text)
            return False, error_msg
    except Exception as e:
        return False, str(e)

def get_all_trails():
    """Fetch all trails from all parks"""
    trails = []
    parks = get_parks()
    session_id = get_session_id()
    
    for park in parks:
        park_id = park.get("park_id")
        if not park_id:
            continue
        
        try:
            resp = requests.get(
                f"{API_BASE}/api/parks/{park_id}/trails",
                cookies={"session_id": session_id},
                timeout=5,
            )
            if resp.status_code == 200:
                park_trails = resp.json().get("trails", [])
                for trail in park_trails:
                    trails.append({
                        "name": trail["name"],
                        "trail_id": trail["trail_id"],
                        "park_name": park["name"],
                        "length_miles": trail.get("length_miles", "N/A"),
                        "difficulty": trail.get("difficulty", "N/A")
                    })
        except Exception as e:
            continue
    
    return trails

def get_trail_name(trail_id):
    """Get trail name by trail_id"""
    trails = get_all_trails()
    for trail in trails:
        if trail["trail_id"] == trail_id:
            return f"{trail['name']} ({trail['park_name']})"
    return f"Trail ID: {trail_id}"

def submit_trail_review(trail_id, rating, comment):
    """Submit a new trail review"""
    try:
        session_id = get_session_id()
        data = {
            "rating": rating,
            "review_text": comment
        }
        response = requests.post(
            f"{API_BASE}/api/trails/{trail_id}/reviews",
            json=data,
            cookies={"session_id": session_id},
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            return True, response.json()
        else:
            error_msg = response.json().get("error", response.text)
            return False, error_msg
    except Exception as e:
        return False, str(e)

def delete_park_review(review_id):
    """Delete a park review"""
    try:
        session_id = get_session_id()
        response = requests.delete(
            f"{API_BASE}/api/parks/reviews/{review_id}",
            cookies={"session_id": session_id},
            timeout=5
        )
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error deleting review: {str(e)}")
        return False

def delete_trail_review(review_id):
    """Delete a trail review"""
    try:
        session_id = get_session_id()
        response = requests.delete(
            f"{API_BASE}/api/trails/reviews/{review_id}",
            cookies={"session_id": session_id},
            timeout=5
        )
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error deleting review: {str(e)}")
        return False

def display_star_rating(rating):
    """Display star rating visually"""
    full_stars = int(rating)
    half_star = 1 if rating - full_stars >= 0.5 else 0
    empty_stars = 5 - full_stars - half_star
    
    stars = "⭐" * full_stars + "✨" * half_star + "☆" * empty_stars
    return f"{stars} ({rating:.1f}/5.0)"

# -------------------------------------------------------------------
# Page Configuration
# -------------------------------------------------------------------
st.title("🌲 Reviews")
st.caption("Share your experiences and help other adventurers!")
st.markdown("---")

# -------------------------------------------------------------------
# Tab Navigation
# -------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["📝 Park Review", "🥾 Trail Review", "📖 My Reviews"])

# -------------------------------------------------------------------
# TAB 1: Park Review
# -------------------------------------------------------------------
with tab1:
    st.header("Write a Park Review")
    
    # Fetch available parks
    parks = get_parks()
    
    if not parks:
        st.warning("No parks available. Please check your connection.")
    else:
        # Park selection
        park_options = {f"{park.get('name', 'Unknown')} - {park.get('state', '')}": park.get('park_id') for park in parks}
        selected_park_display = st.selectbox("Select a Park", options=list(park_options.keys()), key="park_select")
        selected_park_id = park_options[selected_park_display]
        
        # Show park details
        park_detail = get_park_detail(selected_park_id)
        if park_detail:
            with st.expander("View Park Details"):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.write(f"**Location:** {park_detail.get('state', 'N/A')}")
                    st.write(f"**Designation:** {park_detail.get('designation', 'N/A')}")
                with col2:
                    description = park_detail.get('description', 'No description available')
                    st.write(description[:200] + "..." if len(description) > 200 else description)
        
        # Rating input
        rating_park = st.slider("Rating", min_value=1, max_value=5, value=4, step=1, key="park_rating")
        st.caption(display_star_rating(float(rating_park)))
        
        # Comment input
        comment_park = st.text_area(
            "Your Review",
            placeholder="Share your experience at this park...",
            height=150,
            max_chars=1000,
            key="park_comment"
        )
        
        # Submit button
        if st.button("Submit Park Review", type="primary", key="park_submit"):
            if not comment_park.strip():
                st.error("Please write a comment before submitting.")
            else:
                with st.spinner("Submitting review..."):
                    success, result = submit_park_review(selected_park_id, rating_park, comment_park)
                    if success:
                        st.success("✅ Park review submitted successfully!")
                        st.balloons()
                    else:
                        st.error(f"Failed to submit review: {result}")

# -------------------------------------------------------------------
# TAB 2: Trail Review
# -------------------------------------------------------------------
with tab2:
    st.header("Write a Trail Review")
    
    # Fetch available trails
    trails = get_all_trails()
    
    if not trails:
        st.warning("No trails available. Please check your connection.")
    else:
        # Trail selection
        trail_options = {f"{trail['name']} ({trail['park_name']}) - {trail['difficulty']} - {trail['length_miles']} mi": trail['trail_id'] for trail in trails}
        selected_trail_display = st.selectbox("Select a Trail", options=list(trail_options.keys()), key="trail_select")
        selected_trail_id = trail_options[selected_trail_display]
        
        # Find the selected trail details
        selected_trail = next((t for t in trails if t['trail_id'] == selected_trail_id), None)
        
        if selected_trail:
            with st.expander("View Trail Details"):
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.write(f"**Park:** {selected_trail['park_name']}")
                    st.write(f"**Length:** {selected_trail['length_miles']} miles")
                with col2:
                    st.write(f"**Difficulty:** {selected_trail['difficulty']}")
        
        # Rating input
        rating_trail = st.slider("Rating", min_value=1, max_value=5, value=4, step=1, key="trail_rating")
        st.caption(display_star_rating(float(rating_trail)))
        
        # Comment input
        comment_trail = st.text_area(
            "Your Review",
            placeholder="Share your experience on this trail...",
            height=150,
            max_chars=1000,
            key="trail_comment"
        )
        
        # Submit button
        if st.button("Submit Trail Review", type="primary", key="trail_submit"):
            if not comment_trail.strip():
                st.error("Please write a comment before submitting.")
            else:
                with st.spinner("Submitting review..."):
                    success, result = submit_trail_review(selected_trail_id, rating_trail, comment_trail)
                    if success:
                        st.success("✅ Trail review submitted successfully!")
                        st.balloons()
                    else:
                        st.error(f"Failed to submit review: {result}")

# -------------------------------------------------------------------
# TAB 3: My Reviews
# -------------------------------------------------------------------
with tab3:
    st.header("My Reviews")
    
    # Fetch both park and trail reviews
    park_reviews = get_user_park_reviews()
    trail_reviews = get_user_trail_reviews()
    
    total_reviews = len(park_reviews) + len(trail_reviews)
    
    if total_reviews == 0:
        st.info("You haven't written any reviews yet. Head to the Park Review or Trail Review tabs to get started!")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Park Reviews", len(park_reviews))
        with col2:
            st.metric("Trail Reviews", len(trail_reviews))
        
        st.markdown("---")
        
        # Display Park Reviews
        if park_reviews:
            st.subheader("🏞️ Park Reviews")
            for idx, review in enumerate(park_reviews):
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        park_name = review.get('park_name', f"Park ID: {review.get('park_id')}")
                        st.write(f"**{park_name}**")
                        st.caption(display_star_rating(review.get('rating', 0)))
                        st.write(review.get('review_text', 'No comment'))
                        created_at = review.get('created_at', '')
                        if created_at:
                            st.caption(f"📅 {created_at[:10]}")
                    
                    with col2:
                        if st.button("🗑️ Delete", key=f"delete_park_{idx}"):
                            if delete_park_review(review.get('review_id')):
                                st.success("Review deleted!")
                                st.rerun()
                            else:
                                st.error("Failed to delete review")
                    
                    st.markdown("---")
        
        # Display Trail Reviews
        if trail_reviews:
            st.subheader("🥾 Trail Reviews")
            for idx, review in enumerate(trail_reviews):
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        trail_name = get_trail_name(review.get('trail_id'))
                        st.write(f"**{trail_name}**")
                        st.caption(display_star_rating(review.get('rating', 0)))
                        st.write(review.get('review_text', 'No comment'))
                        created_at = review.get('created_at', '')
                        if created_at:
                            st.caption(f"📅 {created_at[:10]}")
                    
                    with col2:
                        if st.button("🗑️ Delete", key=f"delete_trail_{idx}"):
                            if delete_trail_review(review.get('review_id')):
                                st.success("Review deleted!")
                                st.rerun()
                            else:
                                st.error("Failed to delete review")
                    
                    st.markdown("---")

# -------------------------------------------------------------------
# Footer
# -------------------------------------------------------------------
st.markdown("---")
st.caption("💚 Help fellow adventurers by sharing your experiences!")