from datetime import datetime
from app.schemas.projects.projects import ProjectCard
from app.services.projects.curation import compute_curation


def test_compute_curation() -> None:
    # 1. Test feature action (Flagship with repo)
    project_flagship = ProjectCard(
        id="1",
        name="Flagship App",
        tagline="A flagship",
        description="A great flagship project with repository",
        stack=["Python", "FastAPI"],
        capabilities=["Testing"],
        tier="Flagship Project",
        is_featured=True,
        status="completed",
        rating=4.5,
        updated_at=datetime.now(),
        has_repo=True,
        link_status="confirmed"
    )

    # 2. Test keep action (Flagship without repo)
    project_no_repo = ProjectCard(
        id="2",
        name="No Repo Flagship",
        tagline="A flagship without repo",
        description="A flagship project without repository",
        stack=["Python"],
        capabilities=["Testing"],
        tier="Flagship Project",
        is_featured=False,
        status="completed",
        rating=4.5,
        updated_at=datetime.now(),
        has_repo=False,
        link_status="unmatched"
    )

    # 3. Test keep action (Standard career project)
    project_career = ProjectCard(
        id="3",
        name="Career App",
        tagline="A career app",
        description="A standard career project",
        stack=["React"],
        capabilities=[],
        tier="Career Project",
        is_featured=False,
        status="completed",
        rating=3.5,
        updated_at=datetime.now(),
        has_repo=True,
        link_status="confirmed"
    )

    # 4. Test hide suggested action
    project_learning = ProjectCard(
        id="4",
        name="Learning App",
        tagline="A learning app",
        description="A learning project",
        stack=["HTML"],
        capabilities=[],
        tier="Prototype",
        is_featured=False,
        status="completed",
        rating=2.0,
        updated_at=datetime.now(),
        has_repo=False,
        link_status="unmatched"
    )

    # Compute curation with 4 projects (no dilution warning expected)
    res = compute_curation([project_flagship, project_no_repo, project_career, project_learning])
    assert len(res["items"]) == 4
    assert res["dilution_warning"] is None

    # Check actions
    actions = {item["project_id"]: item["action"] for item in res["items"]}
    assert actions["1"] == "feature"
    assert actions["2"] == "keep"
    assert actions["3"] == "keep"
    assert actions["4"] == "hide_suggested"

    # Add more hide_suggested projects to trigger dilution warning (total > 4 and weak_count >= 3)
    project_learning_2 = ProjectCard(
        id="5",
        name="Learning App 2",
        tagline="Another learning app",
        description="Another learning project",
        stack=["CSS"],
        capabilities=[],
        tier="Prototype",
        is_featured=False,
        status="completed",
        rating=1.5,
        updated_at=datetime.now(),
        has_repo=False,
        link_status="unmatched"
    )
    project_learning_3 = ProjectCard(
        id="6",
        name="Learning App 3",
        tagline="Third learning app",
        description="Third learning project",
        stack=["CSS"],
        capabilities=[],
        tier="Prototype",
        is_featured=False,
        status="completed",
        rating=1.5,
        updated_at=datetime.now(),
        has_repo=False,
        link_status="unmatched"
    )

    res_diluted = compute_curation([
        project_flagship,
        project_no_repo,
        project_career,
        project_learning,
        project_learning_2,
        project_learning_3
    ])
    assert len(res_diluted["items"]) == 6
    assert res_diluted["dilution_warning"] is not None
    assert "low-evidence" in res_diluted["dilution_warning"].lower()
