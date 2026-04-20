import { TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router";
import { getVisibleConfigHealthIssues, useConfigHealth } from "@/api/system";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

export function ConfigHealthBanner() {
  const { t } = useTranslation();
  const { data: configHealth } = useConfigHealth();

  const visibleIssues = getVisibleConfigHealthIssues(configHealth).slice(0, 3);
  const hasError = visibleIssues.some((issue) => issue.level === "error");

  if (visibleIssues.length === 0) {
    return null;
  }

  const descriptionKey = configHealth?.primary_provider
    ? "general.configHealth.descriptionWithProvider"
    : "general.configHealth.description";

  return (
    <Alert
      variant={hasError ? "destructive" : "default"}
      className={cn(
        "border",
        !hasError &&
          "border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-amber-100",
      )}
    >
      <TriangleAlert className="size-4" />
      <AlertTitle className="flex flex-wrap items-center gap-2">
        {t("general.configHealth.title")}
      </AlertTitle>
      <AlertDescription>
        <p>
          {t(descriptionKey, {
            provider: configHealth?.primary_provider,
          })}{" "}
          <NavLink
            to="/setting"
            className="font-medium underline underline-offset-4"
          >
            {t("general.configHealth.openModels")}
          </NavLink>
        </p>
        <ul className="list-disc pl-5">
          {visibleIssues.map((issue) => (
            <li key={`${issue.level}:${issue.scope}:${issue.message}`}>
              <span className="font-medium">{issue.scope}</span>:{" "}
              {issue.message}
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
