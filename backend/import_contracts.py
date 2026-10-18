from typing import Final, Optional

import grimp
from importlinter import Contract, ContractCheck, fields, output
from importlinter.application import contract_utils
from importlinter.domain import helpers
from importlinter.domain.imports import ImportExpression

_Link = tuple[str, str, tuple[Optional[int], ...]]

_ALERT_ON_UNMATCHED_IGNORE: Final[contract_utils.AlertLevel] = contract_utils.AlertLevel.ERROR


class ModuleBoundariesContract(Contract):
    """
    Every direct child of `container` is a module: its own package (`__init__.py`) is public,
    everything below it is importable only from the module itself and `allowed_importers`.
    A new module is covered as soon as it exists.
    """

    type_name = "module_boundaries"

    container = fields.ModuleField()
    allowed_importers = fields.ListField(subfield=fields.ModuleExpressionField())
    ignore_imports = fields.SetField(subfield=fields.ImportExpressionField(), required=False)

    def check(self, graph: grimp.ImportGraph, verbose: bool) -> ContractCheck:
        ignore_imports: Optional[list[ImportExpression]] = self.ignore_imports  # type: ignore[assignment]
        warnings = contract_utils.remove_ignored_imports(
            graph=graph,
            ignore_imports=ignore_imports,
            unmatched_alerting=_ALERT_ON_UNMATCHED_IGNORE,
        )
        allowed = {
            module.name
            for module in helpers.module_expressions_to_modules(
                graph=graph,
                expressions=self.allowed_importers,  # type: ignore[arg-type]
                as_packages=True,
            )
        }

        illegal: list[_Link] = []
        for module in sorted(graph.find_children(self.container.name)):  # type: ignore[attr-defined]
            for imported in sorted(graph.find_descendants(module)):
                for importer in sorted(graph.find_modules_that_directly_import(imported) - allowed):
                    if importer == module or importer.startswith(f"{module}."):
                        continue
                    details = graph.get_import_details(importer=importer, imported=imported)
                    line_numbers = tuple(detail["line_number"] for detail in details)
                    illegal.append((importer, imported, line_numbers))

        return ContractCheck(kept=not illegal, warnings=warnings, metadata={"illegal": illegal})

    def render_broken_contract(self, check: ContractCheck) -> None:
        links: list[_Link] = check.metadata["illegal"]
        for importer, imported, line_numbers in links:
            lines = ", ".join(map(str, line_numbers))
            output.print_error(f"- {importer} -> {imported} (l.{lines})", bold=False)
            output.new_line()
