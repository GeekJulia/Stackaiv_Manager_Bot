def can_activate_program(db):
    result = db.fetch_one(
        "SELECT COUNT(*) FROM program_activations WHERE is_paid = FALSE"
    )
    return result['count'] < 3
