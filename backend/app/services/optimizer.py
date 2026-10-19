from typing import Dict, List, Optional

from app.services.question_generator import quota_for_type

class ILPOptimizer:
    def __init__(self, target_marks: int = 50, include_types: list[str] | None = None):
        self.target_marks = target_marks
        self.include_types = include_types

    def assemble_test(self, candidate_questions: List[Dict]) -> Optional[List[Dict]]:
        """
        Solves the Multiple-Choice Knapsack Problem (MCKP) using Integer Linear Programming (ILP)
        to select a combination of questions that sum exactly to target_marks and maximize quality.
        
        candidate_questions structure:
        [
            {"id": 1, "type": "mcq", "marks": 1, "score": 0.95, "data": {...}},
            ...
        ]
        """
        import pulp
        if not candidate_questions:
            return None

        # 1. Create the ILP Problem (Maximization)
        prob = pulp.LpProblem("Exact_50_Mark_Test_Assembly", pulp.LpMaximize)

        # 2. Decision Variables (x_i in {0, 1})
        # 1 if question i is selected, 0 otherwise
        question_vars = {}
        for q in candidate_questions:
            question_vars[q["id"]] = pulp.LpVariable(f"q_{q['id']}", cat=pulp.LpBinary)

        # 3. Objective Function: Maximize sum of (quality_score * x_i)
        prob += pulp.lpSum([q["score"] * question_vars[q["id"]] for q in candidate_questions])

        # 4. Strict Constraint 1: Exact total marks must equal target_marks (e.g., 50)
        prob += pulp.lpSum([q["marks"] * question_vars[q["id"]] for q in candidate_questions]) == self.target_marks

        # 5. Format Diversity Constraints — only for selected / available types
        def type_included(q_type: str) -> bool:
            if not self.include_types:
                return True
            return q_type in self.include_types

        mcq_ids = [q["id"] for q in candidate_questions if q["type"] == "mcq"]
        if type_included("mcq") and len(mcq_ids) >= 3:
            prob += pulp.lpSum([question_vars[qid] for qid in mcq_ids]) >= min(3, len(mcq_ids))

        ar_ids = [q["id"] for q in candidate_questions if q["type"] == "assertion_reason"]
        if type_included("assertion_reason") and len(ar_ids) >= 2:
            prob += pulp.lpSum([question_vars[qid] for qid in ar_ids]) >= min(2, len(ar_ids))

        tf_ids = [q["id"] for q in candidate_questions if q["type"] == "true_false"]
        if type_included("true_false") and len(tf_ids) >= 2:
            prob += pulp.lpSum([question_vars[qid] for qid in tf_ids]) >= min(2, len(tf_ids))

        fb_ids = [q["id"] for q in candidate_questions if q["type"] == "fill_blank"]
        if type_included("fill_blank") and len(fb_ids) >= 2:
            prob += pulp.lpSum([question_vars[qid] for qid in fb_ids]) >= min(2, len(fb_ids))

        pic_ids = [q["id"] for q in candidate_questions if q["type"] == "picture_match"]
        if type_included("picture_match") and len(pic_ids) >= 1:
            prob += pulp.lpSum([question_vars[qid] for qid in pic_ids]) >= 1

        word_ids = [q["id"] for q in candidate_questions if q["type"] == "word_match"]
        if type_included("word_match") and len(word_ids) >= 1:
            prob += pulp.lpSum([question_vars[qid] for qid in word_ids]) >= 1

        short_ids = [q["id"] for q in candidate_questions if q["type"] == "short_answer"]
        if type_included("short_answer") and len(short_ids) >= 2:
            prob += pulp.lpSum([question_vars[qid] for qid in short_ids]) >= min(2, len(short_ids))

        if self.include_types:
            # Force inclusion of at least 1 of each selected type
            for q_type in self.include_types:
                type_ids = [q["id"] for q in candidate_questions if q["type"] == q_type]
                if type_ids:
                    prob += pulp.lpSum([question_vars[qid] for qid in type_ids]) >= 1
            
            # STRICT EXCLUSION: Do not allow ANY question from unselected types
            for q in candidate_questions:
                if q["type"] not in self.include_types:
                    prob += question_vars[q["id"]] == 0

        # 6. Solve the problem
        # CBC is the default open-source solver shipped with PuLP
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        # 7. Check feasibility
        status = pulp.LpStatus[prob.status]
        if status != "Optimal":
            # Infeasible means no combination of these questions can perfectly hit 50 marks 
            # while satisfying format constraints.
            return None

        # 8. Extract the selected questions
        selected_questions = []
        for q in candidate_questions:
            if pulp.value(question_vars[q["id"]]) == 1.0:
                selected_questions.append(q)

        return selected_questions


def assemble_fixed_per_type(
    candidate_questions: List[Dict],
    include_types: List[str],
    questions_per_type: int = 5,
    total_marks: int = 50,
) -> Optional[List[Dict]]:
    """
    Pick questions per selected format, then allot marks so each format is consistent
    and the paper totals exactly `total_marks`. Match-the-following is 1 mark per pair.
    """
    if not include_types:
        return None

    selected: List[Dict] = []
    for q_type in dict.fromkeys(include_types):
        need = quota_for_type(q_type, questions_per_type)
        type_pool = [q for q in candidate_questions if q["type"] == q_type]
        type_pool.sort(key=lambda q: q.get("score", 0), reverse=True)
        picked = type_pool[:need]
        if len(picked) < need:
            return None
        selected.extend(picked)

    if not selected:
        return None

    allot_consistent_marks(selected, total_marks)
    return selected


MATCH_TYPES = frozenset({"word_match", "picture_match"})


def _pair_count(question: Dict) -> int:
    data = question.get("data") or {}
    q_type = question.get("type")
    if q_type == "picture_match":
        n = max(len(data.get("pictures") or []), len(data.get("labels") or []))
        return n if n else 5
    if q_type == "word_match":
        n = max(len(data.get("column_a") or []), len(data.get("column_b") or []))
        return n if n else 5
    return 1


def _fit_question_counts(selected: List[Dict], total_marks: int) -> List[Dict]:
    """Drop extra questions when the total cannot fund every question at 1 mark.

    Every selected format stays. A 50-mark paper already funds the full set, so
    that paper is left unchanged.
    """
    grouped: List[tuple[str, List[Dict]]] = []
    for question in selected:
        q_type = question.get("type")
        if grouped and grouped[-1][0] == q_type:
            grouped[-1][1].append(question)
        else:
            grouped.append((q_type, [question]))

    match_groups = [(q_type, qs) for q_type, qs in grouped if q_type in MATCH_TYPES]
    other_groups = [(q_type, qs) for q_type, qs in grouped if q_type not in MATCH_TYPES]
    if not other_groups:
        return selected

    natural_match = sum(_pair_count(question) for _, qs in match_groups for question in qs)
    other_count = sum(len(qs) for _, qs in other_groups)
    if natural_match + other_count <= total_marks:
        return selected

    if natural_match < total_marks:
        per_format = (total_marks - natural_match) // len(other_groups)
        per_format = min(per_format, min(len(qs) for _, qs in other_groups))
    else:
        per_format = 1 if total_marks > len(match_groups) else 0
    if per_format < 1:
        return selected

    kept: List[Dict] = []
    for _, qs in match_groups:
        kept.extend(qs)
    for _, qs in other_groups:
        kept.extend(qs[:per_format])
    return kept


def _assign_match_marks(match_qs: List[Dict], budget: int) -> None:
    """1 mark per pair when the budget allows. Otherwise share the budget."""
    caps = [_pair_count(question) for question in match_qs]
    if budget >= sum(caps):
        for question, cap in zip(match_qs, caps):
            question["marks"] = cap
        return
    if budget <= 0:
        for question in match_qs:
            question["marks"] = 0
        return
    marks = [0] * len(match_qs)
    if budget >= len(match_qs):
        marks = [1] * len(match_qs)
        budget -= len(match_qs)
    else:
        for index in range(budget):
            marks[index] = 1
        budget = 0
    while budget > 0:
        progressed = False
        for index, cap in enumerate(caps):
            if budget <= 0:
                break
            if marks[index] < cap:
                marks[index] += 1
                budget -= 1
                progressed = True
        if not progressed:
            break
    for question, mark in zip(match_qs, marks):
        question["marks"] = mark


def allot_consistent_marks(selected: List[Dict], total_marks: int = 50) -> List[Dict]:
    """
    Same format → same marks per question. Match-the-following gets 1 mark per pair
    when the paper can afford it. Leftover extras go to whole formats (never split
    one MCQ at 3 and the next at 2). Totals exactly `total_marks`.
    """
    if not selected:
        return selected

    fitted = _fit_question_counts(selected, total_marks)
    if fitted is not selected:
        selected[:] = fitted

    match_qs = [q for q in selected if q.get("type") in MATCH_TYPES]
    other_qs = [q for q in selected if q.get("type") not in MATCH_TYPES]

    match_budget = total_marks - len(other_qs)
    _assign_match_marks(match_qs, match_budget)

    leftover = total_marks - sum(int(q["marks"]) for q in match_qs)
    if leftover < 0:
        if match_qs:
            match_qs[-1]["marks"] = int(match_qs[-1]["marks"]) + leftover
            leftover = 0
        else:
            leftover = total_marks

    if not other_qs:
        if match_qs:
            match_qs[-1]["marks"] = int(match_qs[-1]["marks"]) + leftover
        return selected

    n = len(other_qs)
    base = leftover // n
    extra = leftover % n
    for q in other_qs:
        q["marks"] = base

    # Spread leftover across match questions so word/picture stay even.
    if extra and match_qs:
        i = 0
        while extra > 0:
            match_qs[i % len(match_qs)]["marks"] = int(match_qs[i % len(match_qs)]["marks"]) + 1
            extra -= 1
            i += 1

    groups: Dict[str, List[Dict]] = {}
    for q in other_qs:
        groups.setdefault(q["type"], []).append(q)

    for qs in groups.values():
        if extra >= len(qs):
            for q in qs:
                q["marks"] = int(q["marks"]) + 1
            extra -= len(qs)

    if extra:
        other_qs[-1]["marks"] = int(other_qs[-1]["marks"]) + extra

    return selected


def structure_final_test_json(
    selected_questions: List[Dict],
    questions_per_type: int = 5,
) -> Dict:
    """
    Groups the selected questions into sections for the frontend.
    Each format is capped at `questions_per_type` so picture-match cannot overflow.
    """
    by_type: Dict[str, List[Dict]] = {}
    for q in selected_questions:
        by_type.setdefault(q["type"], []).append(q)

    def take(q_type: str) -> List[Dict]:
        return by_type.get(q_type, [])[: quota_for_type(q_type, questions_per_type)]

    test_paper = {
        "section_A_MCQs": take("mcq"),
        "section_B_AssertionReason": take("assertion_reason"),
        "section_C_Objective": take("true_false") + take("fill_blank"),
        "section_D_MatchFollowing": take("word_match") + take("picture_match"),
        "section_D_Subjective": take("short_answer"),
        "section_oral": take("oral"),
        "section_who_said": take("who_said"),
        "section_answer_following": take("answer_following"),
        "section_creative": take("creative"),
    }
    return test_paper
