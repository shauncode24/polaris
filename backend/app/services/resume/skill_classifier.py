import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.structure import SkillAlias
from app.schemas.shared.skill_classification import SkillClassificationBatch

# Tier 1: hand-seeded, instant, free. Covers the common cases you already
# know about. Anything not here falls through to tiers 2 and 3 below.
# IMPORTANT: keys must be lowercase — resolve_skills() lowercases raw input
# before this lookup, so all casing variants are handled automatically.
CANONICAL_SKILLS: dict[str, str] = {
    # React — all common surface forms
    "react": "react", "reactjs": "react", "react.js": "react",
    "react js": "react",  # spaced, as LLMs often produce

    # Angular
    "angular": "angular", "angularjs": "angular", "angular.js": "angular",
    "angular js": "angular",

    # Spring Boot / Java
    "spring boot": "spring_boot", "spring-boot": "spring_boot",
    "springboot": "spring_boot", "spring": "spring_boot",
    "java": "java", "java se": "java", "java ee": "java",

    # AWS
    "aws": "aws", "amazon web services": "aws",
    "aws services": "aws", "amazon aws": "aws",

    # Microservices
    "microservices": "microservices", "micro services": "microservices",
    "microservice": "microservices", "microservice architecture": "microservices",

    # Python
    "python": "python",

    # FastAPI
    "fastapi": "fastapi", "fast api": "fastapi",

    # Docker / Kubernetes
    "docker": "docker",
    "kubernetes": "kubernetes", "k8s": "kubernetes",

    # Database
    "redis": "redis",
    "postgres": "postgres", "postgresql": "postgres",
    "mysql": "mysql",
    "mongodb": "mongodb", "mongo": "mongodb",
    "sql server": "sql_server",
    "sql": "sql",

    # Frontend
    "typescript": "typescript", "ts": "typescript",
    "javascript": "javascript", "js": "javascript",
    "html": "html", "html5": "html",
    "css": "css", "css3": "css",
    "vue": "vue", "vue.js": "vue", "vuejs": "vue", "vue js": "vue",

    # Web frameworks
    "asp.net core": "aspnet_core", "asp.netcore": "aspnet_core", "aspnetcore": "aspnet_core",
    "c#": "csharp", "c sharp": "csharp",
    "ef core": "ef_core",
    "node.js": "nodejs", "nodejs": "nodejs", "node": "nodejs", "node js": "nodejs",
    "express.js": "express", "expressjs": "express", "express": "express",
    "three.js": "threejs", "threejs": "threejs",

    # REST
    "rest api": "rest_api", "restful api": "rest_api", "restful_api": "rest_api",
    "rest": "rest_api", "rest apis": "rest_api", "rest_apis": "rest_api",
    "restful": "rest_api", "rest api design": "rest_api",

    # Git
    "git": "git", "git workflows": "git", "github": "github", "gitlab": "gitlab",
    "version control": "git",

    # AI/ML
    "langgraph": "langgraph",
    "rag": "rag",
    "langchain": "langchain",
    "openai": "openai",
    "tensorflow": "tensorflow",
    "pytorch": "pytorch",

    # Vector search
    "vector search": "vector_search",

    # Every spelling below maps to ONE name, because the skill gap matches a
    # job's requirement to a user's evidence on that name alone.

    # Languages
    "go": "go", "golang": "go", "go lang": "go",
    "c": "c", "c++": "cpp", "cpp": "cpp",
    ".net": "dotnet", "dotnet": "dotnet",
    "ruby": "ruby", "rails": "ruby_on_rails", "ruby on rails": "ruby_on_rails",
    "scala": "scala", "rust": "rust", "linux": "linux",

    # Computer-science fundamentals and practices
    "object-oriented programming": "object_oriented_programming",
    "object oriented programming": "object_oriented_programming",
    "object-oriented design": "object_oriented_programming",
    "object oriented design": "object_oriented_programming",
    "oop": "object_oriented_programming", "oops": "object_oriented_programming",
    "data structures": "data_structures", "algorithms": "algorithms",
    "design patterns": "design_patterns",
    "concurrency": "concurrency",
    "multithreading": "multithreading", "multi-threading": "multithreading",
    "distributed systems": "distributed_systems", "distributed system": "distributed_systems",
    "distributed computing": "distributed_systems",
    "testing": "testing", "unit testing": "testing", "unit tests": "testing",
    "debugging": "debugging",
    "api": "api", "apis": "api", "api design": "api", "api development": "api",
    "restful apis": "rest_api", "rest api development": "rest_api",
    "micro-services": "microservices", "micro-services architecture": "microservices",
    "microservices architecture": "microservices",
    "monitoring": "monitoring", "alerting": "alerting", "observability": "observability",
    "ci/cd": "ci_cd", "ci-cd": "ci_cd", "cicd": "ci_cd", "ci cd": "ci_cd",
    "ci/cd pipelines": "ci_cd", "ci/cd pipeline": "ci_cd",
    "infrastructure as code": "infrastructure_as_code",
    "infrastructure-as-code": "infrastructure_as_code", "iac": "infrastructure_as_code",
    "data modeling": "data_modeling", "data modelling": "data_modeling",
    "domain modeling": "data_modeling", "domain modelling": "data_modeling",
    "data pipelines": "data_pipelines", "data pipeline": "data_pipelines",
    "data warehousing": "data_warehousing",
    "big data": "big_data", "big data technologies": "big_data",
    "machine learning": "machine_learning", "ml": "machine_learning",
    "statistics": "statistics", "statistical methods": "statistics",
    "linear algebra": "linear_algebra",
    "threat modeling": "threat_modeling", "threat modelling": "threat_modeling",

    # Cloud
    "gcp": "gcp", "google cloud": "gcp", "google cloud platform": "gcp",
    "azure": "azure", "microsoft azure": "azure", "ms azure": "azure", "msft azure": "azure",
    "s3": "s3", "aws s3": "s3", "amazon s3": "s3",
    "ec2": "ec2", "aws ec2": "ec2", "amazon ec2": "ec2",
    "eks": "eks", "aws eks": "eks", "amazon eks": "eks",
    "sqs": "sqs", "aws sqs": "sqs", "amazon sqs": "sqs",
    "iam": "iam", "aws iam": "iam",
    "rds": "rds", "aws rds": "rds", "amazon rds": "rds",
    "msk": "msk", "aws msk": "msk", "amazon msk": "msk",
    "emr": "emr", "aws emr": "emr", "amazon emr": "emr",
    "redshift": "redshift", "aws redshift": "redshift", "amazon redshift": "redshift",

    # Data and infrastructure tools
    "elasticsearch": "elasticsearch", "elastic search": "elasticsearch",
    "kafka": "kafka", "apache kafka": "kafka",
    "spark": "spark", "apache spark": "spark",
    "airflow": "airflow", "apache airflow": "airflow",
    "flink": "flink", "apache flink": "flink",
    "iceberg": "iceberg", "apache iceberg": "iceberg",
    "hudi": "hudi", "apache hudi": "hudi",
    "superset": "superset", "apache superset": "superset",
    "power bi": "power_bi", "powerbi": "power_bi",
    "scikit-learn": "scikit_learn", "scikit learn": "scikit_learn", "sklearn": "scikit_learn",
    "next.js": "nextjs", "nextjs": "nextjs",
    "argocd": "argocd", "argo cd": "argocd",
    "github actions": "github_actions",
}

from app.prompts.shared.classification import CLASSIFICATION_SYSTEM_PROMPT


async def _classify_via_llm(raw_strings: list[str]) -> dict[str, tuple[str | None, bool]]:
    """One batched LLM call for every raw string not already known, rather
    than one call per skill — keeps this cheap even for a resume with many
    unfamiliar terms.
    """
    user_content = json.dumps(raw_strings)
    response = await chat_completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content
    parsed = SkillClassificationBatch.model_validate(json.loads(content))

    output: dict[str, tuple[str | None, bool]] = {}
    for item in parsed.results:
        output[item.raw] = (item.canonical, item.is_valid_skill)

    # Defensive fallback: if the LLM dropped any input (skipped it in the
    # response), treat it as invalid rather than crashing the ingestion.
    for raw in raw_strings:
        if raw not in output:
            output[raw] = (None, False)

    return output


async def resolve_skills(raw_strings: set[str], db: AsyncSession) -> dict[str, str | None]:
    """Resolve every raw skill string to its canonical name, or None if it's
    not a real skill at all. Three tiers, cheapest first:

    1. Hardcoded dict  -> instant, free, zero DB/LLM calls
    2. skill_aliases DB cache -> instant, free, grows over time as new
       resumes are ingested (by any user)
    3. Batched LLM classification -> only for genuinely unseen strings,
       one call per ingestion run (not per skill), and every result is
       written back into the cache so it's never re-classified again.
    """
    results: dict[str, str | None] = {}
    unresolved: set[str] = set()

    for raw in raw_strings:
        key = raw.strip().lower()
        if key in CANONICAL_SKILLS:
            results[raw] = CANONICAL_SKILLS[key]
        else:
            unresolved.add(raw)

    if unresolved:
        lookup_keys = [r.strip().lower() for r in unresolved]
        cached = await db.execute(
            select(SkillAlias).where(SkillAlias.raw_string.in_(lookup_keys))
        )
        cached_by_key = {row.raw_string: row for row in cached.scalars().all()}

        still_unresolved: set[str] = set()
        for raw in unresolved:
            key = raw.strip().lower()
            if key in cached_by_key:
                row = cached_by_key[key]
                results[raw] = row.canonical_name if row.is_valid_skill else None
            else:
                still_unresolved.add(raw)
        unresolved = still_unresolved

    if unresolved:
        # Sorted so the same set of strings always produces the same request.
        classified = await _classify_via_llm(sorted(unresolved))

        for raw, (canonical, is_valid) in classified.items():
            key = raw.strip().lower()
            results[raw] = canonical if is_valid else None

            # Persist this decision so future ingestions (any user, any
            # resume) never need to ask the LLM about this string again.
            stmt = (
                pg_insert(SkillAlias)
                .values(raw_string=key, canonical_name=canonical, is_valid_skill=is_valid)
                .on_conflict_do_nothing(index_elements=["raw_string"])
            )
            await db.execute(stmt)

        await db.flush()

    return results