import { useState, useCallback, useEffect } from 'react';
import { usersApi, settingsApi } from '../api/client';
import { PageLoader } from '../components/Spinner';
import Modal from '../components/Modal';
import Badge from '../components/Badge';
import { FormField, Input, Select, Btn, ErrorAlert } from '../components/FormComponents';
import { Settings as SettingsIcon, Plus, Edit, Shield, List, Power } from 'lucide-react';
import { format, parseISO } from 'date-fns';

// ── User Modal ────────────────────────────────────────────────────────────────
function UserModal({ existing, onClose, onSaved }) {
  const [form, setForm] = useState({
    username: existing?.username ?? '',
    full_name: existing?.full_name ?? '',
    email: existing?.email ?? '',
    role: existing?.role ?? 'Sales Clerk',
    password: '',
    is_active: existing?.is_active ?? true,
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const save = async () => {
    setError(''); setLoading(true);
    try {
      if (existing) {
        await usersApi.update(existing.user_id, {
          full_name: form.full_name,
          email: form.email || null,
          role: form.role,
          is_active: form.is_active,
        });
      } else {
        await usersApi.create({
          full_name: form.full_name,
          username: form.username,
          password: form.password,
          role: form.role,
          email: form.email || null,
        });
      }
      onSaved();
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to save user');
    } finally { setLoading(false); }
  };

  return (
    <Modal title={existing ? 'Edit User' : 'Create User'} onClose={onClose}
      footer={<><Btn variant="secondary" onClick={onClose}>Cancel</Btn><Btn onClick={save} disabled={loading}>{loading ? 'Saving…' : 'Save'}</Btn></>}>
      <div className="space-y-4">
        <ErrorAlert message={error} />
        <div className="grid grid-cols-2 gap-4">
          <FormField label="Username" required><Input value={form.username} onChange={e => setForm({...form, username: e.target.value})} disabled={!!existing} /></FormField>
          <FormField label="Full Name" required><Input value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} /></FormField>
          <FormField label="Email"><Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} /></FormField>
          <FormField label="Role" required>
            <Select value={form.role} onChange={e => setForm({...form, role: e.target.value})}>
              <option value="Administrator">Administrator</option>
              <option value="Pharmacist">Pharmacist</option>
              <option value="Sales Clerk">Sales Clerk</option>
            </Select>
          </FormField>
          {!existing && (
            <FormField label="Password" required>
              <Input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} placeholder="Min 8 chars, 1 letter, 1 digit" />
            </FormField>
          )}
          {existing && (
            <div className="col-span-2 pt-2">
              <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                <input type="checkbox" checked={form.is_active} onChange={e => setForm({...form, is_active: e.target.checked})} className="rounded text-blue-600" />
                Account Active
              </label>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

export default function SettingsPage() {
  const [tab, setTab] = useState('users');
  const [users, setUsers] = useState([]);
  const [settings, setSettings] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addUser, setAddUser] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [editSetting, setEditSetting] = useState(null);
  const [settingVal, setSettingVal] = useState('');
  const [savingSetting, setSavingSetting] = useState(false);
  const [settingError, setSettingError] = useState('');

  const loadUsers = useCallback(() => {
    setLoading(true);
    usersApi.list().then(r => setUsers(r.data ?? [])).finally(() => setLoading(false));
  }, []);

  const loadSettings = useCallback(() => {
    setLoading(true);
    settingsApi.list().then(r => setSettings(r.data ?? [])).finally(() => setLoading(false));
  }, []);

  const loadAudit = useCallback(() => {
    setLoading(true);
    settingsApi.auditLogs({ limit: 100 }).then(r => setAuditLogs(r.data ?? [])).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (tab === 'users') loadUsers();
    else if (tab === 'params') loadSettings();
    else if (tab === 'audit') loadAudit();
  }, [tab, loadUsers, loadSettings, loadAudit]);

  const handleToggleUser = async (userId) => {
    try {
      await usersApi.toggleStatus(userId);
      loadUsers();
    } catch (err) { alert(err.response?.data?.detail ?? 'Failed to update user status'); }
  };

  const saveSetting = async () => {
    setSettingError(''); setSavingSetting(true);
    try {
      await settingsApi.update(editSetting.setting_key, {
        setting_key: editSetting.setting_key,
        setting_value: settingVal,
      });
      setEditSetting(null);
      loadSettings();
    } catch (err) {
      setSettingError(err.response?.data?.detail ?? 'Failed to update parameter');
    } finally { setSavingSetting(false); }
  };

  const tabs = [
    { id: 'users', label: 'User Management', icon: Shield },
    { id: 'params', label: 'System Parameters', icon: SettingsIcon },
    { id: 'audit', label: 'Security Audit Log', icon: List },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-2 mb-6">
        <SettingsIcon size={22} className="text-blue-600" />
        <h1 className="text-2xl font-bold text-gray-900">System Administration & Settings</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-fast ${tab === id ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
            <Icon size={16} />{label}
          </button>
        ))}
      </div>

      {/* Users */}
      {tab === 'users' && (
        <>
          <div className="flex justify-end mb-4">
            <Btn onClick={() => setAddUser(true)}><Plus size={16} />Create User</Btn>
          </div>
          {loading ? <PageLoader /> : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    {['Username','Full Name','Email','Role','Status','Created At'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">{h}</th>
                    ))}
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.user_id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono font-medium text-xs text-blue-700">{u.username}</td>
                      <td className="px-4 py-3 font-medium text-gray-900">{u.full_name ?? '—'}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{u.email ?? '—'}</td>
                      <td className="px-4 py-3"><Badge label={u.role} /></td>
                      <td className="px-4 py-3"><Badge label={u.is_active ? 'Active' : 'Inactive'} /></td>
                      <td className="px-4 py-3 text-xs text-gray-400">
                        {u.created_at ? format(parseISO(u.created_at), 'dd MMM yyyy') : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1 justify-end">
                          <button onClick={() => setEditUser(u)} className="p-1.5 text-blue-500 hover:bg-blue-50 rounded-lg" title="Edit User">
                            <Edit size={15} />
                          </button>
                          <button onClick={() => handleToggleUser(u.user_id)}
                            className={`p-1.5 rounded-lg ${u.is_active ? 'text-amber-600 hover:bg-amber-50' : 'text-green-600 hover:bg-green-50'}`}
                            title={u.is_active ? 'Deactivate User' : 'Reactivate User'}>
                            <Power size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && <tr><td colSpan={7} className="py-12 text-center text-gray-400">No users found</td></tr>}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Parameters */}
      {tab === 'params' && (
        loading ? <PageLoader /> : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Parameter Key','Current Value','Description','Last Modified'].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">{h}</th>
                  ))}
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {settings.map(s => (
                  <tr key={s.setting_key} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-gray-800">{s.setting_key}</td>
                    <td className="px-4 py-3 font-bold text-blue-700">{s.setting_value}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{s.description ?? '—'}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">
                      {s.updated_at ? format(parseISO(s.updated_at), 'dd MMM yy HH:mm') : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => { setEditSetting(s); setSettingVal(s.setting_value); setSettingError(''); }}
                        className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-lg" title="Edit Parameter">
                        <Edit size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
                {settings.length === 0 && <tr><td colSpan={5} className="py-12 text-center text-gray-400">No parameters found</td></tr>}
              </tbody>
            </table>
          </div>
        )
      )}

      {/* Audit Log */}
      {tab === 'audit' && (
        loading ? <PageLoader /> : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    {['Timestamp','User','Action','Target Entity','Entity ID','Result','IP Address'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.map((log, i) => (
                    <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                        {log.logged_at ? format(parseISO(log.logged_at), 'dd MMM yyyy HH:mm:ss') : '—'}
                      </td>
                      <td className="px-4 py-3 text-xs font-mono font-medium text-gray-900">{log.username ?? `#${log.user_id}`}</td>
                      <td className="px-4 py-3 text-xs font-semibold text-blue-800">{log.action}</td>
                      <td className="px-4 py-3 text-xs text-gray-600">{log.entity ?? '—'}</td>
                      <td className="px-4 py-3 text-xs font-mono text-gray-500">{log.entity_id ?? '—'}</td>
                      <td className="px-4 py-3">
                        <Badge label={log.result === 'Success' ? 'Approved' : 'Rejected'} />
                      </td>
                      <td className="px-4 py-3 text-xs font-mono text-gray-400">{log.ip_address ?? '127.0.0.1'}</td>
                    </tr>
                  ))}
                  {auditLogs.length === 0 && <tr><td colSpan={7} className="py-12 text-center text-gray-400">No audit log records</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        )
      )}

      {addUser && <UserModal onClose={() => setAddUser(false)} onSaved={() => { setAddUser(false); loadUsers(); }} />}
      {editUser && <UserModal existing={editUser} onClose={() => setEditUser(null)} onSaved={() => { setEditUser(null); loadUsers(); }} />}

      {editSetting && (
        <Modal title={`Edit Parameter: ${editSetting.setting_key}`} onClose={() => setEditSetting(null)} size="sm"
          footer={<><Btn variant="secondary" onClick={() => setEditSetting(null)}>Cancel</Btn><Btn onClick={saveSetting} disabled={savingSetting}>{savingSetting ? 'Saving…' : 'Save Changes'}</Btn></>}>
          <div className="space-y-3">
            <ErrorAlert message={settingError} />
            <p className="text-xs text-gray-500 leading-relaxed">{editSetting.description}</p>
            <FormField label="Setting Value" required>
              <Input value={settingVal} onChange={e => setSettingVal(e.target.value)} autoFocus />
            </FormField>
          </div>
        </Modal>
      )}
    </div>
  );
}
