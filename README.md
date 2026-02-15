# KampongKonek - Intergenerational Social Platform

A social media platform designed to enhance intergenerational interactions through forums, posts, and community engagement.

## Features

### User Management
- User registration with email, username, password, birthdate, interests, and bio
- Admin registration with secret key
- Profile pages showing posts, friends, followers, following
- Age displayed publicly to facilitate intergenerational connections

### Posts & Content
- Create posts with text (280 character limit) and images
- Twitter-style reply threads
- Like, comment, repost (with optional quote), and share functionality
- Character counter for post creation
- Real-time feed updates via Socket.IO

### Forums
- Create and join forums (max 5 per user, 7-day account age requirement)
- Public and private forums
- Interest-based forum recommendations
- Search and filter forums by activity, popularity, newest
- Forum-specific posts
- Moderator system with ability to delete posts and ban users

### Social Features
- Friend request system
- Following system
- Notifications for replies, mentions, forum activity, post activity, follows, and friend requests
- Real-time search for users and forums

### Moderation
- Forum moderators can delete posts, warn, and ban users
- Site admins can moderate all content
- Ban appeals system
- Deleted content shows "[deleted by moderator]" message

### Accessibility
- Adjustable font sizes (small, medium, large, extra large)
- High contrast mode
- Accessible controls in settings menu

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: MySQL
- **Templates**: Jinja2
- **Frontend**: HTML, Bootstrap 5, JavaScript
- **Real-time**: Socket.IO
- **Architecture**: Object-Oriented Programming with CRUD operations

## Installation

### Prerequisites
- Python 3.8+
- MySQL 8.0+
- pip

### Setup Steps

1. **Clone or download the project files**

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up MySQL database**
```bash
mysql -u root -p
```

Then run:
```sql
CREATE DATABASE social_media_db;
USE social_media_db;
```

4. **Import the database schema**
```bash
mysql -u root -p social_media_db < db_schema.sql
```

5. **Update database configuration**

Edit `app.py` and update the database credentials:
```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_password',  # Change this
    'database': 'social_media_db'
}
```

6. **Run the application**
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Project Structure

```
project/
├── app.py                      # Main Flask application
├── models.py                   # Database models with CRUD operations
├── requirements.txt            # Python dependencies
├── db_schema.sql              # Database schema
├── templates/
│   ├── base.html              # Base template with navbar and sidebar
│   ├── login.html             # Login page
│   ├── register.html          # User registration
│   ├── admin_register.html    # Admin registration
│   ├── feed.html              # Main feed
│   ├── forums.html            # Forums list
│   ├── forum_detail.html      # Forum detail with posts
│   ├── create_forum.html      # Create new forum
│   ├── profile.html           # User profile
│   ├── friends_list.html      # Friends/Followers/Following list
│   ├── post_detail.html       # Post detail with comments
│   ├── notifications.html     # Notifications page
│   ├── settings.html          # User settings
│   └── forum_search_results.html  # Forum search results
└── README.md                  # This file
```

## Usage

### First-Time Setup

1. **Register an admin account** (optional but recommended):
   - Go to `/admin-register`
   - Use admin secret key: `ADMIN_SECRET_KEY_2025`
   - This gives you full moderation privileges

2. **Register a regular user account**:
   - Go to `/register`
   - Fill in all required fields
   - Select interests for forum recommendations

3. **Explore the platform**:
   - Create posts on your feed
   - Join or create forums
   - Connect with other users

### Creating Forums

Requirements:
- Account must be at least 7 days old
- Maximum 5 forums per account

Steps:
1. Navigate to Forums page
2. Click "Create Forum"
3. Fill in forum details and select interest tags
4. Optionally make the forum private

### Moderating Forums

As a forum creator or moderator:
- Delete inappropriate posts
- Ban users from the forum
- Review ban appeals

### Admin Functions

Site admins can:
- Moderate all posts across all forums
- Ban users site-wide
- Review all reports

## Available Interests

Technology, Sports, Art, Gaming, Cooking, Travel, Entertainment, Identity, Music, Books, Fitness, Fashion, Education, Business, Science, Politics, Health

## Security Features

- Password hashing using Werkzeug
- SQL injection prevention via parameterized queries
- Input validation on all forms
- Character limits on posts and comments
- Account age requirements for forum creation

## Real-Time Features

- Live search as you type in the sidebar
- New posts notification via Socket.IO
- Real-time feed updates

## Accessibility Features

- Four font size options
- High contrast mode
- Semantic HTML
- ARIA labels (can be enhanced further)

## Future Enhancements

Potential features to add:
- Direct messaging system
- Email notifications
- Image upload functionality
- More granular privacy controls
- Advanced search filters
- User blocking
- Post editing
- Forum categories
- Trending topics
- User badges and achievements

## Troubleshooting

### Database Connection Issues
- Ensure MySQL is running
- Verify database credentials in `app.py`
- Check if database and tables exist

### Import Errors
- Run `pip install -r requirements.txt`
- Ensure Python 3.8+ is installed

### Socket.IO Not Working
- Check if port 5000 is available
- Ensure Flask-SocketIO is properly installed

## License

This project is created for educational purposes.

## Contact

For questions or issues, please refer to the project documentation or create an issue in the project repository.