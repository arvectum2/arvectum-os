#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workspace_app.access import P704AccessResolver, provision_workspace_grant
from workspace_app.assets import verify_frontend_assets
from workspace_app.company_asset_copilot import (
    CompanyAssetCopilotContractGate,
    CompanyAssetCopilotEvidenceSource,
    P1003CompanyAssetCopilotHandlingResolver,
)
from workspace_app.company_asset_governed_provider import (
    P1004OwnerCompanyAssetAdmissionProvider,
    provision_company_asset_admission_grant,
)
from workspace_app.company_asset_library import CompanyAssetLibrary
from workspace_app.company_asset_retrieval import CompanyAssetRetrieval
from workspace_app.company_materials import CompanyMaterialsStore
from workspace_app.company_durable_executors import build_durable_company_governed_executors
from workspace_app.company_generated_output_governed_provider import (
    P1005OwnerCompanyGeneratedOutputPromotionProvider,
    provision_company_generated_output_promotion_grant,
)
from workspace_app.company_generated_outputs import CompanyGeneratedOutputs
from workspace_app.config import WorkspaceSettings
from workspace_app.f11_routes import install_f11_routes
from workspace_app.main import create_app
from workspace_app.p10_05_routes import install_p10_05_routes
from workspace_app.release import load_release


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="P9.03 Arvectum OS Productive Workspace")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="verify current access and release-pinned built frontend")
    provision = sub.add_parser(
        "provision-local-grant", help="create the exact local Workspace shell operational grant"
    )
    provision.add_argument("--confirm", action="store_true")
    admission = sub.add_parser(
        "provision-company-asset-admission-grant",
        help="create only the exact local Company Asset admission authorization grant",
    )
    admission.add_argument("--confirm", action="store_true")
    promotion = sub.add_parser(
        "provision-company-generated-output-promotion-grant",
        help="create only the exact local reviewed generated-output promotion authorization grant",
    )
    promotion.add_argument("--confirm", action="store_true")
    sub.add_parser("serve", help="serve the bounded same-origin SPA+BFF on the configured profile")
    return parser


def _frontend_root() -> Path:
    return Path(__file__).resolve().parent / "workspace_frontend"


def build_workspace_app(settings: WorkspaceSettings):
    """Build one same-origin Workspace app with bounded Company product routes.

    P10.04 asset admission and P10.05 reviewed-output promotion are installed by
    default on the ADR-0002 product-local durable state pair. Each consequential
    operation remains fail-closed until its own exact P7.04 Authorization grant
    has been explicitly provisioned. Neither persistence nor either grant
    supplies Organizational Authority or Consequential Approval.

    This is only the existing Company asset/output route composition required by
    R34. It does not implement or pre-empt the broader P10.08 operational
    entry-point composition step.
    """

    admission, promotion = build_durable_company_governed_executors(settings.runtime_root)
    materials = CompanyMaterialsStore(Path(settings.runtime_root))
    library = CompanyAssetLibrary(materials, admission)
    retrieval = CompanyAssetRetrieval(library, materials)
    company_copilot_source = CompanyAssetCopilotEvidenceSource(
        library,
        retrieval,
        P1003CompanyAssetCopilotHandlingResolver(admission),
        CompanyAssetCopilotContractGate.current(),
    )
    app = create_app(settings, supplemental_copilot_sources=(company_copilot_source,))
    app = install_f11_routes(
        app,
        asset_admission=admission,
        materials_store=materials,
        asset_library=library,
    )
    outputs = CompanyGeneratedOutputs(
        settings.runtime_root,
        app.state.company_materials_store,
        admission,
        promotion,
    )
    return install_p10_05_routes(app, outputs=outputs)


def main() -> None:
    args = _parser().parse_args()
    settings = WorkspaceSettings.from_env()
    release = load_release()
    if args.command == "provision-local-grant":
        if not args.confirm:
            raise SystemExit("--confirm is required; access is never auto-granted")
        grant_id = provision_workspace_grant(settings.runtime_root)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "grant_id": grant_id,
                    "organizational_authority_provided": False,
                },
                sort_keys=True,
            )
        )
        return
    if args.command == "provision-company-asset-admission-grant":
        if not args.confirm:
            raise SystemExit("--confirm is required; consequential-operation access is never auto-granted")
        grant_id = provision_company_asset_admission_grant(settings.runtime_root)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "grant_id": grant_id,
                    "operation": "company.asset.admit-staged-version",
                    "authorization_only": True,
                    "organizational_authority_provided": False,
                    "consequential_approval_provided": False,
                },
                sort_keys=True,
            )
        )
        return
    if args.command == "provision-company-generated-output-promotion-grant":
        if not args.confirm:
            raise SystemExit("--confirm is required; consequential-operation access is never auto-granted")
        grant_id = provision_company_generated_output_promotion_grant(settings.runtime_root)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "grant_id": grant_id,
                    "operation": "company.generated-output.promote-reviewed",
                    "authorization_only": True,
                    "organizational_authority_provided": False,
                    "consequential_approval_provided": False,
                },
                sort_keys=True,
            )
        )
        return
    if args.command == "check":
        access = P704AccessResolver(settings.runtime_root).authorize()
        assets = verify_frontend_assets(_frontend_root(), release)
        admission_provider = P1004OwnerCompanyAssetAdmissionProvider(settings.runtime_root)
        promotion_provider = P1005OwnerCompanyGeneratedOutputPromotionProvider(settings.runtime_root)
        print(
            json.dumps(
                {
                    **assets,
                    "organization_scope": access.organization.value,
                    "actor_attributable": True,
                    "operational_access_only": True,
                    "company_asset_admission_authorized": admission_provider.available(access),
                    "company_generated_output_promotion_authorized": promotion_provider.available(access),
                    "organizational_authority_provided": False,
                    "public_origin": settings.public_origin,
                },
                sort_keys=True,
            )
        )
        return
    verify_frontend_assets(_frontend_root(), release)
    import uvicorn

    uvicorn.run(
        build_workspace_app(settings),
        host=settings.bind_host,
        port=settings.bind_port,
        proxy_headers=False,
        server_header=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
