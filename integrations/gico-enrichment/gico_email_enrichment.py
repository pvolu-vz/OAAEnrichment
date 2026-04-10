#!/usr/bin/env python3
"""
GICO User Email Enrichment — Veza OAA Enrichment Script

Queries all OAA.GICO.User entities from a Veza tenant, constructs a new custom
attribute called `new_email` by appending a configurable domain suffix to each
user's `native_id`, then pushes the enriched values back to Veza via the OAA
Enrichment (entity_enrichment) template.

Data flow:
  Veza (OAA.GICO.User entities)  →  derive new_email = native_id + domain  →  Veza (enriched attribute)
"""

import argparse
import json
import logging
import os
import sys

from dotenv import load_dotenv
from oaaclient.client import OAAClient, OAAResponseError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENTITY_TYPE = "OAA.GICO.User"
DEFAULT_EMAIL_DOMAIN = "@smurfitwestrock.com"
PROVIDER_NAME = "GICO Email Enrichment"

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enrichment class
# ---------------------------------------------------------------------------

class GICOEmailEnrichment:
    """
    Queries Veza for all OAA.GICO.User entities, builds a `new_email` value
    from each user's native_id, and provides a push-ready payload for the
    OAA Enrichment endpoint.
    """

    entity_type = ENTITY_TYPE

    def __init__(self, veza_client: OAAClient, email_domain: str = DEFAULT_EMAIL_DOMAIN) -> None:
        self._veza_client = veza_client
        self._email_domain = email_domain
        # Maps entity_id -> {data_source_id, native_id, new_email}
        self._enriched_users: dict = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process(self) -> None:
        """Query Veza and build the enrichment map."""
        self._query_gico_users()

    def has_enriched_entities(self) -> bool:
        """Return True if at least one user was successfully enriched."""
        return bool(self._enriched_users)

    def get_push_payload(self) -> dict:
        """Return the OAA Enrichment payload dict ready for push_metadata."""
        return {
            "enriched_entity_property_definitions": [
                {
                    "entity_type": self.entity_type,
                    "enriched_properties": {
                        "new_email": "STRING",
                    },
                },
            ],
            "enriched_entities": [
                {
                    "type": self.entity_type,
                    "id": entity_id,
                    "data_source_id": values["data_source_id"],
                    "properties": {
                        "new_email": values["new_email"],
                    },
                }
                for entity_id, values in self._enriched_users.items()
            ],
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _query_gico_users(self) -> None:
        """Call the Veza query API to fetch all OAA.GICO.User nodes."""

        query = {
            "no_relation": False,
            "include_nodes": True,
            "query_type": "SOURCE_TO_DESTINATION",
            "source_node_types": {
                "nodes": [
                    {
                        "node_type": self.entity_type,
                        "tags_to_get": [],
                        "direct_relationship_only": False,
                    }
                ]
            },
            "node_relationship_type": "EFFECTIVE_ACCESS",
            "result_value_type": "SOURCE_NODES_WITH_COUNTS",
            "include_all_source_tags_in_results": False,
            "include_all_destination_tags_in_results": False,
            "include_sub_permissions": False,
            "include_permissions_summary": True,
        }

        log.info("Querying Veza for all %s entities (page_size=10000)...", self.entity_type)

        try:
            entities = self._veza_client.api_post(
                api_path="/api/v1/assessments/query_spec:nodes",
                data=query,
                params={"page_size": 10_000},
            )
        except OAAResponseError as exc:
            log.error(
                "Veza query failed: %s — %s (HTTP %s)",
                exc.error,
                exc.message,
                exc.status_code,
            )
            if hasattr(exc, "details"):
                for detail in exc.details:
                    log.error("  Detail: %s", detail)
            sys.exit(1)

        entity_list = entities if isinstance(entities, list) else []
        log.info("Received %d %s entities from Veza", len(entity_list), self.entity_type)

        skipped_no_datasource = 0
        skipped_no_native_id = 0

        for entity in entity_list:
            entity_id = entity.get("id")
            props = entity.get("properties") or {}

            if not entity_id:
                log.warning("Skipping entity with missing id field: %s", entity)
                continue

            datasource_id = props.get("datasource_id")
            if not datasource_id:
                log.debug("Skipping entity %s: missing datasource_id", entity_id)
                skipped_no_datasource += 1
                continue

            native_id = props.get("native_id")
            if not native_id:
                log.debug("Skipping entity %s: missing native_id (props: %s)", entity_id, list(props.keys()))
                skipped_no_native_id += 1
                continue

            new_email = f"{native_id}{self._email_domain}"

            self._enriched_users[entity_id] = {
                "data_source_id": datasource_id,
                "native_id": native_id,
                "new_email": new_email,
            }

            log.debug("Prepared: entity_id=%s  native_id=%s  new_email=%s", entity_id, native_id, new_email)

        if skipped_no_datasource:
            log.warning("Skipped %d entities with no datasource_id", skipped_no_datasource)
        if skipped_no_native_id:
            log.warning("Skipped %d entities with no native_id", skipped_no_native_id)

        log.info(
            "Enrichment ready for %d / %d GICO users",
            len(self._enriched_users),
            len(entity_list),
        )


# ---------------------------------------------------------------------------
# Run / push logic
# ---------------------------------------------------------------------------

def run(
    veza_host: str,
    veza_api_key: str,
    email_domain: str,
    save_json: bool,
    dry_run: bool,
) -> None:
    """
    Main execution: query GICO users, build enrichment payload, push to Veza.
    """

    log.info("Connecting to Veza at %s", veza_host)
    veza = OAAClient(url=veza_host, api_key=veza_api_key)

    enrichment = GICOEmailEnrichment(veza_client=veza, email_domain=email_domain)
    enrichment.process()

    if not enrichment.has_enriched_entities():
        log.warning("No GICO users found to enrich — nothing to push.")
        return

    payload = enrichment.get_push_payload()
    entity_count = len(payload["enriched_entities"])
    log.info("Enrichment payload contains %d entities", entity_count)

    if dry_run:
        log.info("[DRY RUN] Skipping Veza push — printing payload preview below.")
        preview = json.dumps(payload, indent=2)
        # Truncate preview so it doesn't flood the terminal
        if len(preview) > 3000:
            preview = preview[:3000] + "\n... (truncated — use --save-json for full output)"
        log.info("[DRY RUN] Payload preview:\n%s", preview)
        return

    provider_name = PROVIDER_NAME
    data_source_name = provider_name

    # Create or retrieve the enrichment provider
    provider = veza.get_provider(name=provider_name)
    if provider:
        provider_id = provider["id"]
        log.info("Using existing provider '%s' (id: %s)", provider_name, provider_id)
    else:
        provider = veza.create_provider(
            name=provider_name, custom_template="entity_enrichment"
        )
        provider_id = provider["id"]
        log.info("Created new provider '%s' (id: %s)", provider_name, provider_id)

    # Push enrichment data
    try:
        veza.push_metadata(
            provider_name=provider_name,
            data_source_name=data_source_name,
            metadata=payload,
            save_json=save_json,
        )
        log.info(
            "Successfully pushed new_email enrichment for %d GICO users to Veza",
            entity_count,
        )
    except OAAResponseError as exc:
        log.error(
            "Veza push_metadata failed: %s — %s (HTTP %s)",
            exc.error,
            exc.message,
            exc.status_code,
        )
        if hasattr(exc, "details"):
            for detail in exc.details:
                log.error("  Detail: %s", detail)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enrich OAA.GICO.User entities in Veza with a derived `new_email` "
            "attribute built from native_id + email domain suffix."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--env-file",
        default=".env",
        metavar="PATH",
        help="Path to a .env file to load (optional).",
    )
    parser.add_argument(
        "--veza-host",
        default=None,
        metavar="HOST",
        help="Veza tenant hostname, e.g. acme.veza.com (or set VEZA_URL).",
    )
    parser.add_argument(
        "--email-domain",
        default=DEFAULT_EMAIL_DOMAIN,
        metavar="DOMAIN",
        help="Domain suffix appended to native_id to form new_email.",
    )
    parser.add_argument(
        "--provider-name",
        default=PROVIDER_NAME,
        metavar="NAME",
        help="OAA provider name as it will appear in the Veza UI.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and preview the enrichment payload without pushing to Veza.",
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Save the enrichment payload to a local JSON file before pushing.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set the logging verbosity level.",
    )

    return parser.parse_args()


def load_config(args: argparse.Namespace) -> dict:
    """Load credentials from .env file then env vars, CLI args take precedence."""
    if args.env_file and os.path.exists(args.env_file):
        load_dotenv(args.env_file)
        log.debug("Loaded env file: %s", args.env_file)

    veza_host = args.veza_host or os.getenv("VEZA_URL") or os.getenv("VEZA_HOST")
    veza_api_key = os.getenv("VEZA_API_KEY")

    missing = []
    if not veza_host:
        missing.append("--veza-host / VEZA_URL")
    if not veza_api_key:
        missing.append("VEZA_API_KEY")

    if missing:
        log.error("Missing required configuration: %s", ", ".join(missing))
        sys.exit(2)

    return {
        "veza_host": veza_host,
        "veza_api_key": veza_api_key,
    }


def main() -> None:
    print(
        "\n"
        "  ╔══════════════════════════════════════════════════════╗\n"
        "  ║   GICO → Veza  |  OAA Email Enrichment  v1.0        ║\n"
        "  ║   Attribute: new_email = native_id + domain          ║\n"
        "  ╚══════════════════════════════════════════════════════╝\n"
    )

    args = parse_args()

    log.setLevel(getattr(logging, args.log_level))

    config = load_config(args)

    run(
        veza_host=config["veza_host"],
        veza_api_key=config["veza_api_key"],
        email_domain=args.email_domain,
        save_json=args.save_json,
        dry_run=args.dry_run,
    )

    log.info("GICO email enrichment completed.")


if __name__ == "__main__":
    main()
