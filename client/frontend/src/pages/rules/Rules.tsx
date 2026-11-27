import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { PageHeader } from '../../components/layout/PageHeader';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Card } from '../../components/ui/Card';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { Table, type Column } from '../../components/ui/Table';
import { useAsyncData } from '../../hooks/useAsyncData';
import { getErrorMessage } from '../../services/api';
import {
  RULE_ACTION_TYPES,
  RULE_OPERATORS,
  ruleService,
  type Rule,
} from '../../services/rule';

const schema = z.object({
  sensor_field: z.string().trim().min(1, 'Informe o campo do sensor'),
  operator: z.enum(RULE_OPERATORS, { error: 'Selecione um operador' }),
  threshold: z.coerce.number({ error: 'Informe um número válido' }),
  action_type: z.enum(RULE_ACTION_TYPES, { error: 'Selecione uma ação' }),
});

// `z.coerce.number` aceita strings do input e devolve number; separar entrada
// e saída mantém o resolver e o submit corretamente tipados.
type RuleFormInput = z.input<typeof schema>;
type RuleForm = z.output<typeof schema>;

const operatorOptions = RULE_OPERATORS.map((value) => ({
  value,
  label: value,
}));

const actionOptions = [
  { value: 'downlink', label: 'Downlink' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'email', label: 'E-mail' },
];

const columns: Column<Rule>[] = [
  { key: 'sensor_field', header: 'Campo do sensor' },
  { key: 'operator', header: 'Operador' },
  { key: 'threshold', header: 'Limite' },
  { key: 'action_type', header: 'Ação' },
];

export default function Rules() {
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RuleFormInput, unknown, RuleForm>({
    resolver: zodResolver(schema),
    defaultValues: {
      sensor_field: '',
      operator: '>',
      threshold: 0,
      action_type: 'downlink',
    },
  });

  const { data, error, loading, reload } = useAsyncData(ruleService.list, []);
  const rules = data ?? [];

  async function submit(values: RuleForm) {
    try {
      await ruleService.create(values);
      reset();
      reload();
    } catch (err) {
      setError('root', { message: getErrorMessage(err) });
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Regras de Negócio"
        description="Cadastre regras de telemetria e seus acionamentos (UC07)."
      />

      {errors.root && (
        <Alert variant="error" className="mb-4">
          {errors.root.message}
        </Alert>
      )}

      <Card
        title="Nova regra"
        action={
          <Button
            type="submit"
            form="rule-form"
            loading={isSubmitting}
            className="px-3 py-1.5"
          >
            Criar regra
          </Button>
        }
      >
        <form
          id="rule-form"
          className="space-y-4"
          onSubmit={handleSubmit(submit)}
        >
          <Input
            label="Campo do sensor"
            placeholder="Ex.: temperatura"
            error={errors.sensor_field?.message}
            {...register('sensor_field')}
          />
          <Select
            label="Operador"
            options={operatorOptions}
            error={errors.operator?.message}
            {...register('operator')}
          />
          <Input
            label="Limite"
            type="number"
            step="any"
            error={errors.threshold?.message}
            {...register('threshold', { valueAsNumber: true })}
          />
          <Select
            label="Ação"
            options={actionOptions}
            error={errors.action_type?.message}
            {...register('action_type')}
          />
        </form>
      </Card>

      <Card title="Regras existentes">
        {loading && (
          <div className="flex justify-center py-8">
            <Spinner size="lg" />
          </div>
        )}

        {!loading && error && (
          <Alert variant="error" onRetry={reload}>
            {error}
          </Alert>
        )}

        {!loading && !error && rules.length === 0 && (
          <EmptyState
            title="Nenhuma regra cadastrada"
            description="Crie a primeira regra para disparar ações quando a telemetria violar o limite."
          />
        )}

        {!loading && !error && rules.length > 0 && (
          <Table columns={columns} rows={rules} rowKey={(rule) => rule.id} />
        )}
      </Card>
    </div>
  );
}
