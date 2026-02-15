import os
import json
import random
import traceback
import logging
from datetime import datetime, timedelta, date, time
from flask import Blueprint, render_template, request, url_for, redirect, session, flash, jsonify, current_app, send_from_directory
from werkzeug.utils import secure_filename
from duckduckgo_search import DDGS
import AIHelper

from events import (
    db_helper, ai_agent, kw_model, SEED_KEYWORDS, BLOCKED_KEYWORDS,
    parse_date_filters, compute_end_time, format_date, format_date_range,
    format_time_12hr, format_date_simple, build_image_url,
    _update_user_interest_weights, _get_user_interests_dict, calculate_match_score
)

event_bp = Blueprint('events', __name__)

def get_project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@event_bp.app_template_filter('fromjson')
def fromjson_filter(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}

@event_bp.route("/media/<path:filename>")
def media_file(filename):
    return send_from_directory(os.path.join(get_project_root(), "media"), filename)

@event_bp.route("/switch_user/<int:user_id>")
def switch_user(user_id):
    user = db_helper.get_user_by_id(user_id)
    if user:
        session["user_id"] = user[0]
        session["user_name"] = user[1]
        session["user_role"] = user[2]
    return redirect(request.referrer or url_for("events.events"))

@event_bp.route("/assets/logo.png")
def logo_png():
    return send_from_directory(os.path.join(get_project_root(), "media"), "KampongKonek.png")

@event_bp.route("/events/edit/<int:event_id>", methods=["POST"])
def events_edit(event_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    conn = db_helper._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT host_id FROM events WHERE event_id = ?", (event_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row or row[0] != session["user_id"]:
        flash("You are not authorized to edit this event.")
        return redirect(url_for(".events"))
        
    event_name = request.form.get("event_name", "").strip()
    event_type = request.form.get("event_type")
    visibility = request.form.get("visibility")
    enable_group_chat = request.form.get("enable_group_chat") == "1"
    enable_minigames = request.form.get("enable_minigames") == "1"
    
    image_source = request.form.get("image_source")
    ai_image_url = request.form.get("ai_image_url")
    image_path = None
    
    if image_source == "upload":
        file = request.files.get("event_image")
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(get_project_root(), "media", "uploads")
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            unique_filename = f"{int(datetime.now().timestamp())}_{filename}"
            file.save(os.path.join(upload_folder, unique_filename))
            image_path = f"uploads/{unique_filename}"
    elif image_source == "ai":
        image_path = ai_image_url

    if not event_name or not event_type or not visibility:
        flash("Missing required fields.")
        return redirect(url_for(".events"))

    full_row = db_helper.get_event_by_id(event_id)
    if not full_row:
        flash("Event not found")
        return redirect(url_for(".events"))
        
    final_image_source = image_source if image_source else full_row[10]
    final_image_path = image_path if image_path else full_row[11]
    final_ai_theme = full_row[12]
    
    updated_event = {
        "event_name": event_name,
        "start_date": request.form.get("start_date") or full_row[2],
        "end_date": request.form.get("end_date") or full_row[3],
        "start_time": request.form.get("start_time") or full_row[4],
        "end_time": request.form.get("end_time") or full_row[5],
        "location": request.form.get("location") or full_row[6],
        "description": full_row[7],
        "visibility": visibility,
        "event_type": event_type,
        "image_source": final_image_source,
        "image_path": final_image_path,
        "ai_theme": final_ai_theme,
        "event_code": full_row[13],
    }
    
    updated_features = {
        "enable_group_chat": enable_group_chat,
        "enable_minigames": enable_minigames
    }
    
    db_helper.update_event(event_id, updated_event, updated_features)
    flash("Event updated successfully.")
    
    return redirect(request.referrer or url_for(".events"))

@event_bp.route("/events/delete/<int:event_id>", methods=["POST"])
def events_delete(event_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    event = db_helper.get_event_by_id(event_id)
    if not event:
        flash("Event not found.")
        return redirect(url_for(".events"))
    
    conn = db_helper._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT host_id FROM events WHERE event_id = ?", (event_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row or row[0] != session["user_id"]:
        flash("You are not authorized to delete this event.")
        return redirect(url_for(".events"))

    if db_helper.delete_event(event_id):
        flash("Event deleted successfully.")
    else:
        flash("Failed to delete event.")
        
    return redirect(url_for(".events"))

@event_bp.route("/events/join_code", methods=["POST"])
def events_join_code():
    if "user_id" not in session:
        return redirect(url_for(".events"))
    
    code = request.form.get("event_code", "").strip()
    if not code:
        flash("Please enter an event code.")
        return redirect(url_for(".events"))
        
    row = db_helper.get_event_by_code(code)
    if not row:
        flash("Invalid event code.")
        return redirect(url_for(".events"))
    
    event_id = row[0]
    visibility = row[8]

    if db_helper.is_user_joined(event_id, session["user_id"]):
        flash("You have already joined this event.")
    else:
        if visibility == 'private':
             db_helper.join_event(event_id, session["user_id"], status="pending")
             flash("Request sent! Waiting for host approval.")
        else:
             db_helper.join_event(event_id, session["user_id"])
             flash("Successfully joined event!")
        
    return redirect(url_for(".events_your_events"))

@event_bp.route("/events")
def events():
    q = request.args.get("q", "").strip()
    date_filter = request.args.get("date", "any")
    type_filter = request.args.get("type", "any")

    filter_start = None
    filter_end = None
    
    if date_filter == "custom":
        fs = request.args.get("start_date")
        fe = request.args.get("end_date")
        if fs:
            try:
                filter_start = datetime.strptime(fs, "%Y-%m-%d").date()
            except ValueError:
                pass
        if fe:
            try:
                filter_end = datetime.strptime(fe, "%Y-%m-%d").date()
            except ValueError:
                pass
    elif date_filter != "any":
        filter_start, filter_end = parse_date_filters(date_filter)
    
    if "user_id" not in session:
        user = db_helper.get_user_by_id(1)
        if user:
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_role"] = user[2]
    
    current_user_id = session.get("user_id")
    current_user_row = db_helper.get_user_by_id(current_user_id)
    
    all_users = db_helper.get_all_users()
    rows = db_helper.get_all_events()
    events_list = []
    
    user_interests_dict = _get_user_interests_dict(current_user_id) if current_user_id else {}

    for row in rows:
        (
            event_id, event_name, start_date, end_date, start_time, end_time,
            location, description, visibility, event_type,
            image_source, image_path, ai_theme, event_code,
            created_at, updated_at, enable_group_chat, enable_minigames,
            interest_tags, host_id
        ) = row

        if type_filter == "online" and event_type != "online":
            continue
        if type_filter == "physical" and event_type != "physical":
            continue

        if filter_start or filter_end:
            try:
                e_start = datetime.strptime(start_date, "%Y-%m-%d").date()
                e_end = datetime.strptime(end_date, "%Y-%m-%d").date()
                
                if filter_start and e_end < filter_start:
                    continue
                if filter_end and e_start > filter_end:
                    continue
            except (ValueError, TypeError):
                continue
            
        if q:
            search_term = q.lower()
            fields = [
                event_name, description, location, ai_theme, interest_tags
            ]
            match_found = False
            for field in fields:
                if field and search_term in field.lower():
                    match_found = True
                    break
            if not match_found:
                continue

        final_image_url = build_image_url(image_source, image_path)
        
        user_status = None
        if current_user_id:
            user_status = db_helper.get_participant_status(event_id, current_user_id)
        
        match_score = calculate_match_score(user_interests_dict, description, interest_tags)
        
        events_list.append({
            "event_id": event_id,
            "event_code": event_code,
            "title": event_name,
            "location": location,
            "description": description,
            "type": "Online" if event_type == "online" else "Physical",
            "visibility": visibility,
            "start_date": start_date,
            "end_date": end_date,
            "start_time": start_time,
            "end_time": end_time,
            "date_line": format_date_range(start_date, end_date),
            "display_date": format_date_simple(start_date),
            "display_start_time": format_time_12hr(start_time),
            "display_end_time": format_time_12hr(end_time),
            "image_url": final_image_url,
            "enable_group_chat": enable_group_chat,
            "enable_minigames": enable_minigames,
            "user_status": user_status,
            "is_joined": user_status == 'going',
            "match_score": match_score,
            "created_at": created_at,
            "interest_tags": interest_tags,
            "host_id": host_id
        })
    
    events_list.sort(key=lambda x: x["created_at"], reverse=True)
    events_list.sort(key=lambda x: x["start_date"])
    events_list.sort(key=lambda x: x["match_score"], reverse=True)

    return render_template(
        "events/events_discover.html",
        events=events_list,
        q=q,
        date_filter=date_filter,
        type_filter=type_filter,
        current_user=session,
        all_users=all_users
    )

@event_bp.route("/events/join/<int:event_id>")
def events_join(event_id):
    if "user_id" not in session:
        return redirect(url_for(".events"))
        
    user_id = session["user_id"]
    current_status = db_helper.get_participant_status(event_id, user_id)
    
    if current_status == "going":
        return redirect(request.referrer or url_for(".events"))
        
    db_helper.join_event(event_id, user_id, status="going")
    
    if current_status is None:
        _update_user_interest_weights(user_id, event_id)

    flash("Successfully joined event!")
    return redirect(request.referrer or url_for(".events"))

@event_bp.route("/events/interested/<int:event_id>")
def events_interested(event_id):
    if "user_id" not in session:
        return redirect(url_for(".events"))
        
    user_id = session["user_id"]
    current_status = db_helper.get_participant_status(event_id, user_id)
    
    if current_status == "going":
        flash("You have already joined this event.")
        return redirect(request.referrer or url_for(".events"))
    elif current_status == "interested":
        db_helper.leave_event(event_id, user_id)
        _update_user_interest_weights(user_id, event_id, delta=-1)
        flash("Removed from your interests.")
        return redirect(request.referrer or url_for(".events"))
        
    db_helper.join_event(event_id, user_id, status="interested")
    _update_user_interest_weights(user_id, event_id, delta=1)
    
    flash("Marked as interested!")
    return redirect(request.referrer or url_for(".events"))

@event_bp.route("/events/leave/<int:event_id>")
def events_leave(event_id):
    if "user_id" not in session:
        return redirect(url_for(".events"))
        
    user_id = session["user_id"]
    current_status = db_helper.get_participant_status(event_id, user_id)
    if not current_status:
        return redirect(request.referrer or url_for(".events"))
        
    db_helper.leave_event(event_id, user_id)
    _update_user_interest_weights(user_id, event_id, delta=-1)
    
    if current_status == "going":
        flash("You have left the event.")
    else:
        flash("Removed from your interests.")
        
    return redirect(request.referrer or url_for(".events"))

def render_user_events(title, visibility_filter=None):
    if "user_id" not in session:
        return redirect(url_for(".events"))
    
    user_id = session["user_id"]
    rows = db_helper.get_user_events(user_id, visibility_filter)
    
    events_list = []
    for row in rows:
        (
            event_id, event_name, start_date, end_date, start_time, end_time,
            location, description, visibility, event_type,
            image_source, image_path, ai_theme, event_code,
            created_at, updated_at, enable_group_chat, enable_minigames,
            interest_tags, host_id, status
        ) = row
        
        final_image_url = build_image_url(image_source, image_path)
            
        events_list.append({
            "event_id": event_id,
            "event_code": event_code,
            "title": event_name,
            "location": location,
            "description": description,
            "type": "Online" if event_type == "online" else "Physical",
            "visibility": visibility,
            "start_date": start_date,
            "end_date": end_date,
            "start_time": start_time,
            "end_time": end_time,
            "date_line": format_date_range(start_date, end_date),
            "display_date": format_date_simple(start_date),
            "display_start_time": format_time_12hr(start_time),
            "display_end_time": format_time_12hr(end_time),
            "image_url": final_image_url,
            "enable_group_chat": enable_group_chat,
            "enable_minigames": enable_minigames,
            "user_status": status,
            "is_joined": status == 'going',
            "host_id": host_id
        })
        
    return render_template(
        "events/events_user_list.html",
        events=events_list,
        page_title=title,
        current_user=session
    )

@event_bp.route("/events/your-events")
def events_your_events():
    return render_user_events("Your Events")

@event_bp.route("/events/public-events")
def events_public_events():
    return render_user_events("Public Events", visibility_filter="public")

@event_bp.route("/events/private-events")
def events_private_events():
    return render_user_events("Private Events", visibility_filter="private")

@event_bp.route("/event_notifications")
def event_notifications():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    user_id = session["user_id"]
    rows = db_helper.get_user_upcoming_events(user_id)
    
    events_list = []
    calendar_events = []
    
    for row in rows:
        (
            event_id, event_name, start_date, end_date, start_time, end_time,
            location, description, visibility, event_type,
            image_source, image_path, ai_theme, event_code,
            created_at, updated_at, enable_group_chat, enable_minigames,
            interest_tags, host_id, role
        ) = row
        
        final_image_url = build_image_url(image_source, image_path)
            
        try:
            start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            display_date = start_date_obj.strftime("%a, %d %b %Y")
        except ValueError:
            display_date = start_date

        event_dict = {
            "event_id": event_id,
            "event_code": event_code,
            "title": event_name,
            "location": location,
            "type": "Online" if event_type == "online" else "Physical",
            "visibility": visibility,
            "start_date": start_date,
            "end_date": end_date,
            "start_time": start_time,
            "end_time": end_time,
            "display_date": display_date,
            "display_start_time": format_time_12hr(start_time),
            "display_end_time": format_time_12hr(end_time),
            "image_url": final_image_url,
            "role": role,
            "user_status": role,
            "host_id": host_id,
            "description": description,
            "event_type": event_type,
            "enable_group_chat": enable_group_chat,
            "enable_minigames": enable_minigames
        }
        events_list.append(event_dict)
        
        cal_event = {
            "title": event_name,
            "start": f"{start_date}T{start_time}",
            "url": url_for('.events_detail', event_code=event_code),
            "color": "#ffc107" if role == 'host' else ("#28a745" if role == 'going' else "#0d6efd"),
            "textColor": "#000" if role == 'host' else "#fff"
        }
        if end_date and end_time:
             cal_event["end"] = f"{end_date}T{end_time}"
             
        calendar_events.append(cal_event)
        
    pending_rows = db_helper.get_pending_join_requests(user_id)
    pending_requests = []
    for pr in pending_rows:
        pending_requests.append({
            "participant_id": pr[0],
            "event_id": pr[1],
            "event_name": pr[2],
            "user_id": pr[3],
            "user_name": pr[4],
            "joined_at": pr[5]
        })
    
    host_stats = db_helper.get_host_stats(user_id)
    smart_suggestions = db_helper.get_smart_suggestions(user_id)
    recent_activity = db_helper.get_recent_activity(user_id)
    signups_over_time = []
    events_mix = []
    if session.get("user_role") == "admin":
        signups_over_time = db_helper.get_signups_over_time(user_id, 30)
        events_mix = db_helper.get_events_type_visibility_breakdown(user_id)

    return render_template(
        "events/event_notifications.html", 
        events=events_list, 
        calendar_events=calendar_events, 
        pending_requests=pending_requests, 
        current_user=session,
        host_stats=host_stats,
        smart_suggestions=smart_suggestions,
        recent_activity=recent_activity,
        signups_over_time=signups_over_time,
        events_mix=events_mix
    )

@event_bp.route("/events/request/approve/<int:participant_id>")
def events_request_approve(participant_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    row = db_helper.get_participant_by_id(participant_id)
    if not row:
        flash("Request not found.")
        return redirect(url_for(".event_notifications"))
        
    event_id = row[1]
    event = db_helper.get_event_by_id(event_id)
    if not event or event[18] != session["user_id"]:
        flash("Unauthorized action.")
        return redirect(url_for(".event_notifications"))
        
    db_helper.update_participant_status(participant_id, "going")
    flash("Request approved!")
    return redirect(url_for(".event_notifications"))

@event_bp.route("/events/request/reject/<int:participant_id>")
def events_request_reject(participant_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    row = db_helper.get_participant_by_id(participant_id)
    if not row:
        flash("Request not found.")
        return redirect(url_for(".event_notifications"))
        
    event_id = row[1]
    event = db_helper.get_event_by_id(event_id)
    if not event or event[18] != session["user_id"]:
        flash("Unauthorized action.")
        return redirect(url_for(".event_notifications"))
        
    db_helper.delete_participant(participant_id)
    flash("Request rejected.")
    return redirect(url_for(".event_notifications"))

@event_bp.route("/events/request/approve-all")
def events_request_approve_all():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    user_id = session["user_id"]
    count = db_helper.approve_all_pending_requests(user_id)
    
    if count > 0:
        flash(f"Approved {count} request(s)!")
    else:
        flash("No pending requests to approve.")
        
    return redirect(url_for(".event_notifications"))

@event_bp.route("/events/request/reject-all")
def events_request_reject_all():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    user_id = session["user_id"]
    count = db_helper.reject_all_pending_requests(user_id)
    
    if count > 0:
        flash(f"Rejected {count} request(s).")
    else:
        flash("No pending requests to reject.")
        
    return redirect(url_for(".event_notifications"))

@event_bp.route("/events/<event_code>")
def events_detail(event_code):
    event = db_helper.get_event_details_by_code(event_code)
    if not event:
        flash("Event not found")
        return redirect(url_for(".events"))

    event["image_url"] = build_image_url(event.get("image_source"), event.get("image_path"))

    start_date_obj = None
    if event.get("start_date"):
        try:
            start_date_obj = datetime.strptime(event["start_date"], "%Y-%m-%d")
            event["start_date_obj"] = start_date_obj
            event["display_date"] = start_date_obj.strftime("%d %b %Y")
        except ValueError:
            pass

    date_range_parts = []
    if event.get("start_date") and event.get("start_time"):
         start_dt_str = f"{format_date_simple(event['start_date'])} at {event['start_time']}"
         date_range_parts.append(start_dt_str)
    
    if event.get("end_date") and event.get("end_time"):
         end_dt_str = f"{format_date_simple(event['end_date'])} at {event['end_time']}"
         date_range_parts.append(end_dt_str)
    
    event["date_range_str"] = " – ".join(date_range_parts)

    duration_str = ""
    try:
        start_dt = datetime.strptime(f"{event['start_date']} {event['start_time']}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{event['end_date']} {event['end_time']}", "%Y-%m-%d %H:%M")
        diff = end_dt - start_dt
        days = diff.days
        seconds = diff.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        parts = []
        if days > 0: parts.append(f"{days} days")
        if hours > 0: parts.append(f"{hours} hours")
        if minutes > 0: parts.append(f"{minutes} minutes")
        
        duration_str = ", ".join(parts)
    except Exception:
        pass
    event["duration"] = duration_str

    user_status = None
    if "user_id" in session:
        user_status = db_helper.get_participant_status(event["event_id"], session["user_id"])

    counts = db_helper.get_event_participant_counts(event["event_id"])

    return render_template("events/event_details.html", event=event, user_status=user_status, counts=counts, current_user=session)

def _get_new_event():
    return session.get("new_event", {})

def _set_new_event(data):
    session["new_event"] = {**_get_new_event(), **data}

@event_bp.route("/events/create/type", methods=["GET", "POST"])
def events_create_type():
    if request.method == "POST":
        event_type = request.form.get("event_type")
        if event_type not in ("physical", "online"):
            flash("Please select event type")
            return render_template("create_event/step1.html")
        _set_new_event({"event_type": event_type})
        return redirect(url_for(".events_create_details"))
    return render_template("create_event/step1.html", new_event=_get_new_event())

@event_bp.route("/events/create/details", methods=["GET", "POST"])
def events_create_details():
    if request.method == "POST":
        event_name = request.form.get("event_name", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        start_time = request.form.get("start_time", "").strip()
        end_time = request.form.get("end_time", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        visibility = request.form.get("visibility")

        errors = []
        if not event_name: errors.append("Event name is required")
        if not start_date: errors.append("Start date is required")
        if not end_date: errors.append("End date is required")
        if not start_time: errors.append("Start time is required")
        if not end_time: errors.append("End time is required")
        if not location: errors.append("Location is required")
        if not description: errors.append("Description is required")
        if visibility not in ("private", "public"): errors.append("Visibility must be private or public")
        
        if start_date and end_date and end_date < start_date:
            errors.append("End date cannot be before start date")
        
        if start_time and end_time and end_time <= start_time:
            errors.append("Daily end time must be after start time")

        if errors:
            for e in errors: flash(e)
            return render_template("create_event/step2.html", new_event=_get_new_event())

        private_code = request.form.get("private_code")
        if visibility == "private":
            if not private_code:
                private_code = f"KK-{random.randint(1000000000, 9999999999)}"

        _set_new_event({
            "event_name": event_name,
            "start_date": start_date,
            "end_date": end_date,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
            "description": description,
            "visibility": visibility,
            "private_code": private_code if visibility == "private" else None,
        })
        return redirect(url_for(".events_create_image"))
    return render_template("create_event/step2.html", new_event=_get_new_event())

@event_bp.route("/events/create/image/fetch", methods=["GET"])
def events_create_image_fetch():
    try:
        description = request.args.get("description")
        explicit_query = request.args.get("query")
        
        offset = request.args.get("offset", 0, type=int)
        
        if explicit_query:
            query = explicit_query
        else:
            if not description:
                description = _get_new_event().get("description", "")
            
            if not description:
                return jsonify({"error": "No description found."}), 400

            if 'kw_model' not in globals():
                 pass 
                 
            keywords_list = kw_model.extract_keywords(
                description, 
                keyphrase_ngram_range=(1, 2), 
                stop_words='english', 
                top_n=3
            )
            
            search_terms = [k[0] for k in keywords_list]
            query = " ".join(search_terms) + " event singapore"
        
        with DDGS() as ddgs:
            results = list(ddgs.images(
                query, 
                region="sg-en", 
                safesearch="moderate", 
                max_results=offset + 2
            ))
            
            if results and len(results) > offset:
                image_url = results[offset].get("image")
                return jsonify({
                    "image_url": image_url, 
                    "query": query,
                    "offset": offset
                })
            else:
                 return jsonify({"error": "No more images found for this query"}), 404
                 
    except Exception as e:
        error_msg = f"Image search error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        with open("error_log.txt", "a") as f:
            f.write(f"\n--- Error at {datetime.now()} ---\n")
            f.write(error_msg)
            
        return jsonify({"error": str(e)}), 500

@event_bp.route("/api/ai-agent/upload-image", methods=["POST"])
def api_ai_agent_upload_image():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file uploaded"}), 400
        
    filename = secure_filename(file.filename)
    upload_folder = os.path.join(get_project_root(), "media", "uploads")
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
        
    unique_filename = f"{int(datetime.now().timestamp())}_{filename}"
    file_path = os.path.join(upload_folder, unique_filename)
    file.save(file_path)
    
    relative_path = f"uploads/{unique_filename}"
    
    return jsonify({
        "path": relative_path,
        "url": url_for("media_file", filename=relative_path)
    })

@event_bp.route("/events/create/image", methods=["GET", "POST"])
def events_create_image():
    if request.method == "POST":
        image_source = request.form.get("image_source")
        image_path = request.form.get("image_path", "").strip() or None
        ai_image_url = request.form.get("ai_image_url", "").strip() or None

        if image_source not in ("upload", "ai"):
            flash("Please select an image source")
            return render_template("create_event/step3.html", new_event=_get_new_event())
        
        if image_source == "upload":
            file = request.files.get("event_image")
            if file and file.filename:
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(get_project_root(), "media", "uploads")
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                
                unique_filename = f"{int(datetime.now().timestamp())}_{filename}"
                file.save(os.path.join(upload_folder, unique_filename))
                
                image_path = f"uploads/{unique_filename}"
            elif not image_path:
                flash("Please choose an image file")
                return render_template("create_event/step3.html", new_event=_get_new_event())

        if image_source == "ai":
            if not ai_image_url:
                flash("Please generate/select an image first")
                return render_template("create_event/step3.html", new_event=_get_new_event())
            image_path = ai_image_url

        _set_new_event({
            "image_source": image_source,
            "image_path": image_path,
            "ai_theme": None 
        })
        return redirect(url_for(".events_create_features"))
    return render_template("create_event/step3.html", new_event=_get_new_event())

@event_bp.route("/events/create/features", methods=["GET", "POST"])
def events_create_features():
    data = _get_new_event()
    if not data.get("event_type"):
        flash("Please select an event type first.")
        return redirect(url_for(".events_create_type"))
    required_details = ["event_name", "start_date", "end_date", "start_time", "end_time", "location", "description", "visibility"]
    if any(not data.get(k) for k in required_details):
        flash("Please fill in all event details.")
        return redirect(url_for(".events_create_details"))
    if not data.get("image_source"):
        flash("Please select an event image.")
        return redirect(url_for(".events_create_image"))

    if request.method == "POST":
        enable_group_chat = 1 if request.form.get("enable_group_chat") == "1" else 0
        enable_minigames = 1 if request.form.get("enable_minigames") == "1" else 0
        _set_new_event({
            "enable_group_chat": enable_group_chat,
            "enable_minigames": enable_minigames,
        })
        return redirect(url_for(".events_create_review"))
    return render_template("create_event/step4.html", new_event=_get_new_event())

@event_bp.route("/events/create/review", methods=["GET", "POST"])
def events_create_review():
    data = _get_new_event()
    
    if not data.get("event_type"):
        flash("Please select an event type first.")
        return redirect(url_for(".events_create_type"))
        
    required_details = [
        "event_name", "start_date", "end_date", "start_time", "end_time", 
        "location", "description", "visibility"
    ]
    missing_details = [k for k in required_details if not data.get(k)]
    if missing_details:
        flash("Please fill in all event details.")
        return redirect(url_for(".events_create_details"))

    if not data.get("image_source"):
        flash("Please select an event image.")
        return redirect(url_for(".events_create_image"))
        
    if request.method == "POST":
        action = request.form.get("action")
        if action == "back":
            return redirect(url_for(".events_create_features"))

        required = [
            "event_name","start_date","end_date","start_time","end_time","location","description",
            "visibility","event_type","image_source"
        ]
        missing = [k for k in required if not data.get(k)]
        if missing:
            for k in missing: flash(f"Missing field: {k}")
            return redirect(url_for(".events_create_details"))

        try:
            final_code = None
            if data.get("visibility") == "private":
                code = data.get("private_code")
                if not code:
                    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
                    code = "".join(random.choice(chars) for _ in range(6))
                if not code.startswith("KK-"):
                    code = f"KK-{code}"
                data["event_code"] = code
                final_code = code
            else:
                data["event_code"] = None
            
            user_tags = request.form.get("interest_tags", "")
            data["interest_tags"] = user_tags
            
            data["host_id"] = session.get("user_id")

            new_id = db_helper.insert_event(data)
            
            if data.get("visibility") == "public":
                code = f"KK-{new_id}"
                db_helper.set_event_code(new_id, code)
                final_code = code

            db_helper.insert_event_features(new_id, {
                "enable_group_chat": data.get("enable_group_chat", 0),
                "enable_minigames": data.get("enable_minigames", 0),
            })
            session.pop("new_event", None)
            return render_template("create_event/success.html", event_code=final_code)
        except Exception as e:
            flash(f"Failed to save event: {e}")
            return render_template("create_event/step5.html", new_event=data, suggested_tags=data.get("interest_tags", ""))
    
    description = data.get("description", "")
    suggested_tags = data.get("interest_tags", "")
    
    if description and not suggested_tags:
        try:
            keywords = kw_model.extract_keywords(
                description, 
                keyphrase_ngram_range=(1, 1), 
                stop_words='english', 
                top_n=10, 
                seed_keywords=SEED_KEYWORDS
            )
            
            final_tags = []
            for k in keywords:
                word = k[0].lower()
                if word not in BLOCKED_KEYWORDS:
                    final_tags.append(word)

            tags = list(set(final_tags))[:5]
            
            suggested_tags = ",".join(tags)
            _set_new_event({"interest_tags": suggested_tags})
            data = _get_new_event()
        except Exception as e:
            print(f"KeyBERT error: {e}")
            suggested_tags = ""

    ai_result = AIHelper.analyze_event_impact(data)

    return render_template("create_event/step5.html", new_event=data, suggested_tags=suggested_tags, ai_result=ai_result)

@event_bp.route("/events/create/apply-ai", methods=["POST"])
def events_create_apply_ai():
    changes_json = request.form.get("changes")
    if changes_json:
        try:
            changes = json.loads(changes_json)
            current_event = _get_new_event()

            if "description" in changes:
                new_text = changes["description"]
                original_text = current_event.get("description", "")
                if new_text not in original_text:
                    combined_desc = f"{new_text}\n\n{original_text}"
                    changes["description"] = combined_desc
            
            if "duration_minutes" in changes:
                duration_mins = int(changes.pop("duration_minutes"))
                s_time_str = changes.get("start_time", current_event.get("start_time"))
                
                if s_time_str:
                    s_time = datetime.strptime(s_time_str, "%H:%M")
                    e_time = s_time + timedelta(minutes=duration_mins)
                    changes["end_time"] = e_time.strftime("%H:%M")

            _set_new_event(changes)
            flash("AI recommendations applied successfully!")
        except Exception as e:
            flash(f"Error applying changes: {e}")
    return redirect(url_for(".events_create_review"))

@event_bp.route("/events/create/ai-agent", methods=["GET", "POST"])
def events_create_ai_agent():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    
    user_id = session["user_id"]
    
    if request.method == "POST":
        user_prompt = request.form.get("ai_prompt")
        if user_prompt:
            session_id = ai_agent.start_new_session(user_id, user_prompt)
            return redirect(url_for(".events_create_ai_session", session_id=session_id))
    
    past_sessions = db_helper.get_user_ai_sessions(user_id)
    return render_template("create_event/ai_agent/build_with_ai.html", past_sessions=past_sessions)

@event_bp.route("/events/create/ai-agent/<int:session_id>")
def events_create_ai_session(session_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    user_id = session["user_id"]
    
    ai_session = db_helper.get_ai_session(session_id)
    if not ai_session or ai_session["host_id"] != user_id:
        flash("Session not found or unauthorized.")
        return redirect(url_for(".events_create_ai_agent"))
        
    conn = db_helper._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT message_id, role, content, created_at FROM ai_event_messages WHERE session_id = ? ORDER BY message_id ASC", (session_id,))
    rows = cur.fetchall()
    conn.close()
    
    messages = [{"message_id": r[0], "role": r[1], "content": r[2], "created_at": r[3]} for r in rows]
    
    max_msg_id = messages[-1]["message_id"] if messages else 0
    
    current_draft = json.loads(ai_session["current_draft_json"])
    
    session[f"checkpoint_{session_id}"] = {
        "draft": current_draft,
        "max_msg_id": max_msg_id
    }
    
    try:
        impact_result = db_helper.get_latest_impact(session_id)
    except Exception as e:
        print(f"Error fetching impact: {e}")
        impact_result = None

    if not impact_result:
        impact_result = {"score": 0, "label": "Pending", "reasons": [], "changes": []}
    
    return render_template(
        "create_event/ai_agent/build_with_ai_workspace.html",
        session=ai_session,
        messages=messages,
        current_draft=current_draft,
        impact_result=impact_result
    )

@event_bp.route("/events/create/ai-agent/<int:session_id>/revert", methods=["POST"])
def events_revert_ai_session(session_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    ai_session = db_helper.get_ai_session(session_id)
    if not ai_session or ai_session["host_id"] != session["user_id"]:
        flash("Unauthorized.")
        return redirect(url_for(".events_create_ai_agent"))
    
    checkpoint_key = f"checkpoint_{session_id}"
    checkpoint = session.get(checkpoint_key)
    
    if checkpoint:
        draft = checkpoint.get("draft")
        max_msg_id = checkpoint.get("max_msg_id")
        db_helper.revert_session_to_checkpoint(session_id, draft, max_msg_id)
        flash("Changes discarded. Session reverted to start.")
        session.pop(checkpoint_key, None)
    else:
        flash("Could not discard changes (Session expired or new).")
        
    return redirect(url_for(".events_create_ai_agent"))

@event_bp.route("/events/create/ai-agent/<int:session_id>/delete", methods=["POST"])
def events_delete_ai_session(session_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    ai_session = db_helper.get_ai_session(session_id)
    if not ai_session or ai_session["host_id"] != session["user_id"]:
        flash("Unauthorized.")
        return redirect(url_for(".events_create_ai_agent"))
        
    db_helper.delete_ai_session(session_id)
    flash("Session deleted.")
    return redirect(url_for(".events_create_ai_agent"))

@event_bp.route("/api/ai-agent/chat", methods=["POST"])
def api_ai_agent_chat():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    session_id = data.get("session_id")
    message = data.get("message")
    
    if not session_id or not message:
        return jsonify({"error": "Missing data"}), 400
        
    ai_session = db_helper.get_ai_session(session_id)
    if not ai_session or ai_session["host_id"] != session["user_id"]:
        return jsonify({"error": "Unauthorized"}), 403
        
    conn = db_helper._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ai_event_messages WHERE session_id = ?", (session_id,))
    msg_count = cur.fetchone()[0]
    conn.close()

    current_draft = json.loads(ai_session["current_draft_json"])
    session[f"undo_{session_id}"] = current_draft
    
    result = ai_agent.process_turn(session_id, message)
    
    result["requires_approval"] = True if msg_count > 0 else False
    
    return jsonify(result)

@event_bp.route("/api/ai-agent/undo", methods=["POST"])
def api_ai_agent_undo():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    session_id = data.get("session_id")
    
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400
        
    ai_session = db_helper.get_ai_session(session_id)
    if not ai_session or ai_session["host_id"] != session["user_id"]:
        return jsonify({"error": "Unauthorized"}), 403
        
    checkpoint = session.get(f"undo_{session_id}")
    if not checkpoint:
        return jsonify({"error": "No checkpoint found"}), 404
        
    db_helper.update_ai_session_draft(session_id, json.dumps(checkpoint))
    
    conn = db_helper._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT message_id FROM ai_event_messages WHERE session_id = ? ORDER BY message_id DESC LIMIT 2", (session_id,))
    rows = cur.fetchall()
    for row in rows:
        cur.execute("DELETE FROM ai_event_messages WHERE message_id = ?", (row[0],))
        cur.execute("DELETE FROM ai_event_patches WHERE message_id = ?", (row[0],))
    conn.commit()
    conn.close()
    
    ai_result = AIHelper.analyze_event_impact(checkpoint)
    
    return jsonify({
        "success": True, 
        "draft": checkpoint,
        "impact": ai_result
    })

@event_bp.route("/api/ai-agent/history", methods=["GET"])
def api_ai_agent_history():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400
        
    ai_session = db_helper.get_ai_session(session_id)
    if not ai_session or ai_session["host_id"] != session["user_id"]:
        return jsonify({"error": "Unauthorized"}), 403
        
    messages = db_helper.get_ai_messages(session_id)
    return jsonify({"messages": messages})

@event_bp.route("/api/ai-agent/revert", methods=["POST"])
def api_ai_agent_revert():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    session_id = data.get("session_id")
    message_id = data.get("message_id")
    
    if not session_id or not message_id:
        return jsonify({"error": "Missing parameters"}), 400

    try:
        message_id = int(message_id)
    except ValueError:
        return jsonify({"error": "Invalid message_id"}), 400

    ai_session = db_helper.get_ai_session(session_id)
    if not ai_session or ai_session["host_id"] != session["user_id"]:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        current_draft = ai_agent.revert_session_to_message(session_id, message_id)
        impact = AIHelper.analyze_event_impact(current_draft)
        
        return jsonify({
            "success": True,
            "draft": current_draft,
            "impact": impact
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@event_bp.route("/events/create/ai-agent/<int:session_id>/review", methods=["GET"])
def events_create_ai_review(session_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    ai_session = db_helper.get_ai_session(session_id)
    if not ai_session or ai_session["host_id"] != session["user_id"]:
        flash("Unauthorized.")
        return redirect(url_for(".events"))
        
    draft = json.loads(ai_session["current_draft_json"])
    
    if draft.get("image_url"):
        clean_url = draft["image_url"].strip()
        if not draft.get("image_path"):
            draft["image_path"] = clean_url
        
        if not draft.get("image_source"):
             if clean_url.startswith("http"):
                 draft["image_source"] = "ai"
             else:
                 draft["image_source"] = "upload"

    ai_result = AIHelper.analyze_event_impact(draft)
    
    return render_template(
        "create_event/step5.html", 
        new_event=draft, 
        ai_result=ai_result, 
        from_ai_agent=True,
        ai_session_id=session_id
    )

@event_bp.route("/events/create/ai-agent/<int:session_id>/finalize", methods=["POST"])
def events_create_ai_commit(session_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
        
    ai_session = db_helper.get_ai_session(session_id)
    if not ai_session or ai_session["host_id"] != session["user_id"]:
        flash("Unauthorized.")
        return redirect(url_for(".events"))
        
    draft = json.loads(ai_session["current_draft_json"])
    
    if draft.get("image_url"):
        clean_url = draft["image_url"].strip()
        if not draft.get("image_path"):
            draft["image_path"] = clean_url
        
        if not draft.get("image_source"):
             if clean_url.startswith("http"):
                 draft["image_source"] = "ai"
             else:
                 draft["image_source"] = "upload"

    required = ["event_name", "start_date", "end_date", "start_time", "end_time", "location", "description"]
    missing = [k for k in required if not draft.get(k)]
    if missing:
        flash(f"Cannot finalize: Missing fields {', '.join(missing)}")
        return redirect(url_for(".events_create_ai_review", session_id=session_id))
        
    final_code = None
    if draft.get("visibility") == "private":
        code = draft.get("private_code")
        if not code:
            import random
            chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            code = "".join(random.choice(chars) for _ in range(6))
        if not code.startswith("KK-"):
            code = f"KK-{code}"
        draft["event_code"] = code
        final_code = code
    else:
        draft["event_code"] = None
    
    draft["host_id"] = session["user_id"]
    
    event_id = db_helper.insert_event(draft)
    
    if draft.get("visibility") == "public":
        code = f"KK-{event_id}"
        db_helper.set_event_code(event_id, code)
        final_code = code

    db_helper.insert_event_features(event_id, draft)
    
    draft["event_code"] = final_code
    db_helper.update_ai_session_draft(session_id, json.dumps(draft), status="finalized")
    
    flash("Event created successfully!")
    return render_template("create_event/success.html", event_code=final_code)

@event_bp.route("/create-event")
def create_event_method():
    session.pop("new_event", None)
    return render_template("create_event/method.html")
