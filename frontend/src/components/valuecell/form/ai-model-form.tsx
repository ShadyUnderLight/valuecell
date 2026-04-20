import { useStore } from "@tanstack/react-form";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  useGetModelCatalog,
  useGetModelProviderDetail,
  useGetSortedModelProviders,
} from "@/api/setting";
import { FieldGroup } from "@/components/ui/field";
import { SelectItem } from "@/components/ui/select";
import PngIcon from "@/components/valuecell/icon/png-icon";
import { MODEL_PROVIDER_ICONS } from "@/constants/icons";
import { withForm } from "@/hooks/use-form";

function AIModelFormRender({ form }: { form: any }) {
  const { t } = useTranslation();
  const {
    providers: sortedProviders,
    defaultProvider,
    isLoading: isLoadingProviders,
  } = useGetSortedModelProviders();

  const provider = useStore(form.store, (state: any) => state.values.provider);
  const {
    isLoading: isLoadingModelProviderDetail,
    data: modelProviderDetail,
    refetch: fetchModelProviderDetail,
  } = useGetModelProviderDetail(provider);
  const { isLoading: isLoadingModelCatalog, data: modelCatalog = [] } =
    useGetModelCatalog(provider);

  useEffect(() => {
    if (isLoadingProviders || !defaultProvider) return;
    if (!provider) {
      form.setFieldValue("provider", defaultProvider);
    }
  }, [isLoadingProviders, defaultProvider, provider, form]);

  if (
    isLoadingProviders ||
    isLoadingModelProviderDetail ||
    isLoadingModelCatalog
  ) {
    return <div>Loading...</div>;
  }

  return (
    <FieldGroup className="gap-6">
      <form.AppField
        listeners={{
          onMount: async () => {
            const { data } = await fetchModelProviderDetail();
            form.setFieldValue("api_key", data?.api_key ?? "");
          },
          onChange: async () => {
            const { data } = await fetchModelProviderDetail();

            form.setFieldValue("model_id", data?.default_model_id ?? "");
            form.setFieldValue("api_key", data?.api_key ?? "");
          },
        }}
        name="provider"
      >
        {(field: any) => (
          <field.SelectField label={t("strategy.form.aiModels.platform")}>
            {sortedProviders.map(({ provider }) => (
              <SelectItem key={provider} value={provider}>
                <div className="flex items-center gap-2">
                  <PngIcon
                    src={
                      MODEL_PROVIDER_ICONS[
                        provider as keyof typeof MODEL_PROVIDER_ICONS
                      ]
                    }
                    className="size-4"
                  />
                  {t(`strategy.providers.${provider}`) || provider}
                </div>
              </SelectItem>
            ))}
          </field.SelectField>
        )}
      </form.AppField>

      <form.AppField name="model_id">
        {(field: any) => {
          const catalogByNativeId = new Map(
            modelCatalog.map((entry) => [entry.native_model_id, entry]),
          );
          const models = (modelProviderDetail?.models || []).map((model) => {
            const catalogEntry = catalogByNativeId.get(model.model_id);
            return {
              model_id: model.model_id,
              model_name:
                catalogEntry?.display_name ||
                model.model_name ||
                model.model_id,
              metaLabel:
                catalogEntry?.status && catalogEntry.status !== "stable"
                  ? catalogEntry.status
                  : catalogEntry?.provider || provider,
            };
          });

          return (
            <field.SelectField label={t("strategy.form.aiModels.model")}>
              {models.map((model) => (
                <SelectItem key={model.model_id} value={model.model_id}>
                  <div className="flex w-full items-center justify-between gap-3">
                    <span>{model.model_name}</span>
                    {model.metaLabel ? (
                      <span className="text-muted-foreground text-xs uppercase">
                        {model.metaLabel}
                      </span>
                    ) : null}
                  </div>
                </SelectItem>
              ))}
            </field.SelectField>
          );
        }}
      </form.AppField>

      <form.AppField name="api_key">
        {(field: any) => (
          <field.PasswordField
            label={t("strategy.form.aiModels.apiKey.label")}
            placeholder={t("strategy.form.aiModels.apiKey.placeholder")}
          />
        )}
      </form.AppField>
    </FieldGroup>
  );
}

export const AIModelForm = withForm({
  defaultValues: {
    model_id: "",
    provider: "",
    api_key: "",
  },

  render({ form }) {
    return <AIModelFormRender form={form} />;
  },
});
