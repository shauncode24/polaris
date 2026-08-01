from app.services.leetcode.leetcode_reviewer import _flag_ungrounded_company_mentions

def test_flag_ungrounded_company_mentions() -> None:
    # Google is in COMPANY_TOPIC_WEIGHTS, Apple is not but is in _COMMONLY_HALLUCINATED_COMPANIES.
    text_with_google = "Google requires dynamic programming and graphs."
    text_with_apple = "Apple usually asks arrays and hashing."
    text_with_both = "Both Google and Apple have tricky questions."
    
    # Google should not be flagged (not commonly hallucinated or it is in COMPANY_TOPIC_WEIGHTS).
    # Google is in COMPANY_TOPIC_WEIGHTS. Apple is in COMMONLY_HALLUCINATED but not in COMPANY_TOPIC_WEIGHTS (known).
    assert _flag_ungrounded_company_mentions(text_with_google) == []
    
    # Apple is in COMMONLY_HALLUCINATED but not in COMPANY_TOPIC_WEIGHTS.
    assert _flag_ungrounded_company_mentions(text_with_apple) == ["Apple"]
    
    # In both, only Apple is flagged
    assert _flag_ungrounded_company_mentions(text_with_both) == ["Apple"]
