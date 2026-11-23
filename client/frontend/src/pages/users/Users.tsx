import { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  inviteLink,
  userService,
  type InviteOutput,
  type UserOutput,
  type UserRole,
} from '../../services/user';
import { useAsyncData } from '../../hooks/useAsyncData';
import { getErrorMessage } from '../../services/api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Breadcrumbs } from '../../components/ui/Breadcrumbs';
import { Table, type Column } from '../../components/ui/Table';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Modal } from '../../components/ui/Modal';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { EmptyState } from '../../components/ui/EmptyState';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { Plus } from '../../components/ui/icons';

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'member', label: 'Membro' },
  { value: 'admin', label: 'Administrador' },
];

export default function Users() {
  const { tenantId = '' } = useParams();
  const { data, error, loading, reload } = useAsyncData(userService.list, []);

  const [inviting, setInviting] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<UserRole>('member');
  const [inviteResult, setInviteResult] = useState<InviteOutput | null>(null);
  const [editingRole, setEditingRole] = useState<UserOutput | null>(null);
  const [editRole, setEditRole] = useState<UserRole>('member');
  const [deactivating, setDeactivating] = useState<UserOutput | null>(null);
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState('');
  const [actionError, setActionError] = useState('');

  const users = data ?? [];

  function openInvite() {
    setInviteEmail('');
    setInviteRole('member');
    setInviteResult(null);
    setFormError('');
    setInviting(true);
  }

  function openRoleModal(user: UserOutput) {
    setEditRole(user.is_admin ? 'admin' : 'member');
    setFormError('');
    setEditingRole(user);
  }

  async function handleInvite() {
    setFormError('');
    setBusy(true);
    try {
      setInviteResult(
        await userService.invite(tenantId, {
          email: inviteEmail.trim(),
          role: inviteRole,
        }),
      );
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRoleChange() {
    if (!editingRole) return;
    setFormError('');
    setBusy(true);
    try {
      await userService.updateRole(editingRole.id, editRole);
      setEditingRole(null);
      reload();
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeactivate() {
    if (!deactivating) return;
    setActionError('');
    setBusy(true);
    try {
      await userService.deactivate(deactivating.id);
      setDeactivating(null);
      reload();
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const columns: Column<UserOutput>[] = [
    {
      key: 'email',
      header: 'E-mail',
      render: (user) => (
        <span className="font-medium text-slate-800">{user.email}</span>
      ),
    },
    {
      key: 'role',
      header: 'Papel',
      render: (user) => (
        <Badge color={user.is_admin ? 'blue' : 'gray'}>
          {user.is_admin ? 'Administrador' : 'Membro'}
        </Badge>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (user) => (
        <Badge color={user.is_active ? 'green' : 'red'}>
          {user.is_active ? 'Ativo' : 'Inativo'}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: 'Ações',
      render: (user) => (
        <div className="flex flex-wrap gap-1">
          <Button
            variant="ghost"
            aria-label={`Alterar papel de ${user.email}`}
            onClick={() => openRoleModal(user)}
          >
            Alterar papel
          </Button>
          <Button
            variant="ghost"
            aria-label={`Desativar ${user.email}`}
            disabled={!user.is_active}
            onClick={() => setDeactivating(user)}
          >
            Desativar
          </Button>
        </div>
      ),
    },
  ];

  const link = inviteResult ? inviteLink(inviteResult) : '';
  const token = inviteResult?.invite_token ?? inviteResult?.token;

  return (
    <div>
      <PageHeader
        title="Usuários"
        description="Gerencie os usuários e os papéis desta organização."
        breadcrumbs={
          <Breadcrumbs
            items={[
              { label: 'Tenants', to: '/tenants' },
              { label: 'Usuários' },
            ]}
          />
        }
        actions={
          <Button onClick={openInvite}>
            <Plus className="h-4 w-4" />
            Convidar usuário
          </Button>
        }
      />

      {actionError && (
        <Alert variant="error" className="mb-4">
          {actionError}
        </Alert>
      )}

      {loading && (
        <div className="flex justify-center py-16">
          <Spinner size="lg" />
        </div>
      )}

      {!loading && error && (
        <Alert variant="error" onRetry={reload}>
          {error}
        </Alert>
      )}

      {!loading && !error && users.length === 0 && (
        <EmptyState
          title="Nenhum usuário encontrado"
          description="Convide um usuário para começar a gerenciar o acesso à organização."
          action={
            <Button onClick={openInvite}>
              <Plus className="h-4 w-4" />
              Convidar usuário
            </Button>
          }
        />
      )}

      {!loading && !error && users.length > 0 && (
        <Table columns={columns} rows={users} rowKey={(user) => user.id} />
      )}

      <Modal
        open={inviting}
        title="Convidar usuário"
        onClose={() => setInviting(false)}
        footer={
          inviteResult ? (
            <Button variant="secondary" onClick={() => setInviting(false)}>
              Fechar
            </Button>
          ) : (
            <>
              <Button
                variant="secondary"
                onClick={() => setInviting(false)}
                disabled={busy}
              >
                Cancelar
              </Button>
              <Button type="submit" form="invite-form" loading={busy}>
                Gerar convite
              </Button>
            </>
          )
        }
      >
        <form
          id="invite-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleInvite();
          }}
          className="space-y-4"
        >
          {formError && <Alert variant="error">{formError}</Alert>}
          <Input
            label="E-mail"
            name="email"
            type="email"
            required
            value={inviteEmail}
            onChange={(event) => setInviteEmail(event.target.value)}
          />
          <Select
            label="Papel"
            name="role"
            options={ROLE_OPTIONS}
            value={inviteRole}
            onChange={(event) => setInviteRole(event.target.value as UserRole)}
          />
          {inviteResult && (
            <div
              role="status"
              className="space-y-2 rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800"
            >
              <p className="font-semibold">Convite gerado com sucesso.</p>
              {link && (
                <a
                  href={link}
                  className="break-all underline underline-offset-2"
                >
                  {link}
                </a>
              )}
              {token && <p className="break-all text-xs">Token: {token}</p>}
            </div>
          )}
        </form>
      </Modal>

      <Modal
        open={editingRole !== null}
        title="Alterar papel"
        onClose={() => setEditingRole(null)}
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setEditingRole(null)}
              disabled={busy}
            >
              Cancelar
            </Button>
            <Button type="submit" form="role-form" loading={busy}>
              Salvar
            </Button>
          </>
        }
      >
        <form
          id="role-form"
          onSubmit={(event) => {
            event.preventDefault();
            void handleRoleChange();
          }}
          className="space-y-4"
        >
          {formError && <Alert variant="error">{formError}</Alert>}
          <p className="text-sm text-muted">
            Usuário: <span className="font-medium">{editingRole?.email}</span>
          </p>
          <Select
            label="Novo papel"
            name="newRole"
            options={ROLE_OPTIONS}
            value={editRole}
            onChange={(event) => setEditRole(event.target.value as UserRole)}
          />
        </form>
      </Modal>

      <ConfirmDialog
        open={deactivating !== null}
        title="Desativar usuário"
        message={`Desativar "${deactivating?.email}"? O usuário perderá o acesso à organização.`}
        confirmLabel="Desativar"
        loading={busy}
        onConfirm={handleDeactivate}
        onCancel={() => setDeactivating(null)}
      />
    </div>
  );
}
