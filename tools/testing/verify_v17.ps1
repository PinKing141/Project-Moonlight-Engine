param(
    [string]$PythonExe = ""
)

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        $PythonExe = $VenvPython
    }
    else {
        $PythonExe = "python"
    }
}

$Tests = @(
    "tests/unit/test_v17_contract_drift.py",
    "tests/unit/test_v17_exploration_facade_delegation.py",
    "tests/unit/test_v17_social_dialogue_facade_delegation.py",
    "tests/unit/test_v17_quest_facade_delegation.py",
    "tests/unit/test_v17_town_economy_facade_delegation.py",
    "tests/unit/test_v17_party_facade_delegation.py",
    "tests/unit/test_architecture_guardrails.py",
    "tests/unit/test_app_contract.py",
    "tests/unit/test_exploration_light_and_suspicion.py",
    "tests/unit/test_town_social_flow.py",
    "tests/unit/test_quest_service.py",
    "tests/unit/test_quest_journal_view.py",
    "tests/unit/test_escalating_quests_and_rumours.py",
    "tests/unit/test_economy_identity_flow.py",
    "tests/unit/test_equipment_management.py",
    "tests/unit/test_live_game_loop_states.py"
)

Push-Location $RepoRoot
try {
    & $PythonExe -m pytest @Tests
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
