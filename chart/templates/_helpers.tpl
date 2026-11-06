{{/*
Expand the name of the chart.
*/}}
{{- define "demo-service.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
