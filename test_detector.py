from app.ml.heuristics import heuristic_analysis


def test_obvious_spam_scores_high():
    p, reasons = heuristic_analysis("CONGRATULATIONS! You have won a $1000 prize. Click here to claim now: http://win.example.com")
    assert p > 0.9 and reasons


def test_normal_message_scores_low():
    p, _ = heuristic_analysis("Hey, are we still meeting for lunch tomorrow?")
    assert p < 0.2


def test_account_bait_flagged():
    p, reasons = heuristic_analysis("Your account is suspended. Verify your password at www.bank-login.top immediately")
    assert p > 0.7 and "Account or security bait" in reasons
