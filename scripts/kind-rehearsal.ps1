param(
  [string]$ClusterName = "data-stream-local",
  [string]$Namespace = "data-stream",
  [string]$OperatorNamespace = "flink",
  [string]$OperatorRepoUrl = "",
  [string]$OperatorChartVersion = "",
  [string]$Manifest = "config/project-manifest.yaml",
  [string]$SiteIds = "",
  [string]$ExportDir = ".\build\kind-rehearsal",
  [string]$PlatformImage = "",
  [string]$KindPath = "",
  [string]$HelmPath = "",
  [string]$KubectlPath = "kubectl",
  [string]$PythonPath = "",
  [switch]$SkipClusterCreate,
  [switch]$SkipOperatorInstall,
  [switch]$EnableOperatorWebhook,
  [switch]$ApplyFlinkDeployment,
  [switch]$DeleteClusterAfter
)

$ErrorActionPreference = "Stop"

function Assert-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $Name"
  }
}

function Resolve-ToolPath {
  param(
    [string]$RequestedPath,
    [string]$ToolName,
    [string[]]$FallbackPatterns
  )

  if ($RequestedPath) {
    return $RequestedPath
  }

  $command = Get-Command $ToolName -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Source
  }

  $searchRoots = @(
    $env:LOCALAPPDATA,
    $env:ProgramFiles,
    ${env:ProgramFiles(x86)}
  ) | Where-Object { $_ }

  foreach ($pattern in $FallbackPatterns) {
    foreach ($root in $searchRoots) {
      $match = Get-ChildItem -Path $root -Recurse -Filter $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($match) {
        return $match.FullName
      }
    }
  }

  throw "Required command not found: $ToolName"
}

function Resolve-PythonCommand {
  param([string]$RequestedPath)

  if ($RequestedPath -and (Test-Path -LiteralPath $RequestedPath)) {
    return $RequestedPath
  }

  $repoRoot = Split-Path -Parent $PSScriptRoot
  $repoPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $repoPython) {
    return $repoPython
  }

  $command = Get-Command python -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Source
  }

  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    return "py"
  }

  throw "Required command not found: python"
}

function Invoke-Checked {
  param(
    [string]$FilePath,
    [string[]]$ArgumentList
  )

  & $FilePath @ArgumentList
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $FilePath $($ArgumentList -join ' ')"
  }
}

function Ensure-Namespace {
  param([string]$Name)

  & $kubectl get namespace $Name | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Invoke-Checked $kubectl @("create", "namespace", $Name)
  }
}

function Update-FlinkDeploymentImage {
  param(
    [string]$ManifestPath,
    [string]$Image,
    [string]$Namespace
  )

  $content = Get-Content -LiteralPath $ManifestPath -Raw
  $updated = $content -replace '(?m)^(\s*image:\s*).+$', "`$1$Image"
  $updated = $updated -replace '(?m)^(\s*namespace:\s*).+$', "`$1$Namespace"
  $tempPath = Join-Path $env:TEMP ("datastream-flinkdeployment-{0}.yaml" -f [Guid]::NewGuid().ToString("N"))
  Set-Content -LiteralPath $tempPath -Value $updated -Encoding utf8
  return $tempPath
}

$kind = Resolve-ToolPath -RequestedPath $KindPath -ToolName "kind" -FallbackPatterns @("kind.exe")
$helm = Resolve-ToolPath -RequestedPath $HelmPath -ToolName "helm" -FallbackPatterns @("helm.exe")
$kubectl = Resolve-ToolPath -RequestedPath $KubectlPath -ToolName "kubectl" -FallbackPatterns @("kubectl.exe")
$python = Resolve-PythonCommand -RequestedPath $PythonPath

Write-Host "Preparing local Kubernetes rehearsal..."

try {
  if (-not $SkipClusterCreate) {
    $clusters = @()
    try {
      $clusters = & $kind get clusters
    }
    catch {
      $clusters = @()
    }

    if ($clusters -notcontains $ClusterName) {
      Invoke-Checked $kind @("create", "cluster", "--name", $ClusterName)
    }
    else {
      Write-Host "Reusing existing kind cluster: $ClusterName"
    }
  }

  if (-not $SkipOperatorInstall) {
    if (-not $OperatorRepoUrl) {
      Write-Host "Operator repository URL not provided; skipping Helm install."
      Write-Host "Install the Apache Flink Kubernetes Operator separately, then rerun with -SkipOperatorInstall or provide -OperatorRepoUrl."
    }
    else {
      Invoke-Checked $helm @("repo", "add", "flink-operator-repo", $OperatorRepoUrl)
      Invoke-Checked $helm @("repo", "update")
      Ensure-Namespace $OperatorNamespace

      $installArgs = @(
        "upgrade", "--install", "flink-kubernetes-operator",
        "flink-operator-repo/flink-kubernetes-operator",
        "--namespace", $OperatorNamespace,
        "--create-namespace"
      )
      if ($OperatorChartVersion) {
        $installArgs += @("--version", $OperatorChartVersion)
      }
      if (-not $EnableOperatorWebhook) {
        # The Apache chart's webhook requires cert-manager. Keep the local
        # rehearsal self-contained; production clusters can opt in when
        # cert-manager is already installed and trusted.
        $installArgs += @("--set", "webhook.create=false")
      }
      Invoke-Checked $helm $installArgs
    }
  }

  $siteIdsArg = @()
  if ($SiteIds) {
    $siteIdsArg = @("--site-ids", $SiteIds)
  }

  New-Item -ItemType Directory -Force -Path $ExportDir | Out-Null
  $reportDir = Join-Path $ExportDir "reports"

  Write-Host "Validating generated Kubernetes bundles..."
  $localRehearsalArgs = @(
    "-m", "services.cli.datastreamctl", "local-kubernetes-rehearsal",
    "--manifest", $Manifest,
    "--export-dir", $ExportDir,
    "--kubectl", $kubectl,
    "--report-dir", $reportDir
  )
  if ($siteIdsArg.Count -gt 0) {
    $localRehearsalArgs += $siteIdsArg
  }
  Invoke-Checked $python $localRehearsalArgs

  if ($ApplyFlinkDeployment) {
    if (-not (Test-Path -LiteralPath "k8s/flink-operator/flinkdeployment.yaml")) {
      throw "Flink deployment manifest not found: k8s/flink-operator/flinkdeployment.yaml"
    }
    if (-not $PlatformImage) {
      throw "PlatformImage is required when -ApplyFlinkDeployment is set"
    }

    try {
      Invoke-Checked $kind @("load", "docker-image", $PlatformImage, "--name", $ClusterName)
    }
    catch {
      Write-Host "Warning: could not load local image into kind: $($_.Exception.Message)"
    }

    Ensure-Namespace $Namespace
    $serviceAccountYaml = & $kubectl create serviceaccount data-stream-flink --namespace $Namespace --dry-run=client -o yaml
    if ($LASTEXITCODE -ne 0) {
      throw "Could not generate Flink service account manifest"
    }
    $serviceAccountYaml | & $kubectl apply -f -
    if ($LASTEXITCODE -ne 0) {
      throw "Could not apply Flink service account manifest"
    }
    $tempManifest = Update-FlinkDeploymentImage -ManifestPath "k8s/flink-operator/flinkdeployment.yaml" -Image $PlatformImage -Namespace $Namespace
    Invoke-Checked $kubectl @("apply", "-f", $tempManifest)
    try {
      Invoke-Checked $kubectl @("wait", "--for=condition=Ready", "flinkdeployment/data-stream-flink-job", "-n", $Namespace, "--timeout=180s")
    }
    catch {
      Write-Host "FlinkDeployment readiness wait did not complete. Inspect the deployment with kubectl if you want to continue manually."
    }
  }
}
finally {
  if ($DeleteClusterAfter) {
    try {
      Invoke-Checked $kind @("delete", "cluster", "--name", $ClusterName)
    }
    catch {
      Write-Host "Warning: could not delete kind cluster: $($_.Exception.Message)"
    }
  }
}

Write-Host "Local Kubernetes rehearsal complete."
