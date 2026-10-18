import { useState } from 'react';
import { Activity, AlertCircle, RefreshCw, Wallet } from 'lucide-react';

const money = (value) => value == null ? 'No limit' : `$${Number(value).toFixed(6)}`;

async function adminRequest(path, adminKey, options = {}) {
  const response = await fetch(`/admin/api${path}`, {
    ...options,
    headers: {
      'X-Admin-API-Key': adminKey,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

export function UsageDashboard() {
  const [adminKey, setAdminKey] = useState('');
  const [teamName, setTeamName] = useState('');
  const [budgetInput, setBudgetInput] = useState('');
  const [usage, setUsage] = useState(null);
  const [keyCount, setKeyCount] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const loadUsage = async (key = adminKey, name = teamName) => {
    if (!key.trim() || !name.trim()) {
      setError('Enter the admin API key and a team name to load usage.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const encodedTeam = encodeURIComponent(name.trim());
      const [usageData, keysData] = await Promise.all([
        adminRequest(`/teams/${encodedTeam}/usage`, key.trim()),
        adminRequest('/keys', key.trim()),
      ]);
      setUsage(usageData);
      setTeamName(usageData.team);
      setBudgetInput(usageData.budgetUsd ?? '');
      setKeyCount(keysData.keys.filter((item) => item.team === usageData.team && !item.revoked).length);
    } catch (requestError) {
      setUsage(null);
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const saveBudget = async (event) => {
    event.preventDefault();
    if (!usage) return;
    setBusy(true);
    setError('');
    try {
      const budget = budgetInput.trim() === '' ? null : Number(budgetInput);
      if (budget !== null && (!Number.isFinite(budget) || budget < 0)) {
        throw new Error('Enter a non-negative monthly budget or leave it blank to remove the limit.');
      }
      await adminRequest(`/teams/${encodeURIComponent(usage.team)}/budget`, adminKey.trim(), {
        method: 'PUT',
        body: JSON.stringify({ budget_monthly_usd: budget }),
      });
      await loadUsage();
    } catch (requestError) {
      setError(requestError.message);
      setBusy(false);
    }
  };

  const spent = Number(usage?.spentUsd ?? 0);
  const reserved = Number(usage?.reservedUsd ?? 0);
  const limit = usage?.budgetUsd == null ? null : Number(usage.budgetUsd);
  const usedPercent = limit && limit > 0 ? Math.min(100, ((spent + reserved) / limit) * 100) : 0;

  return (
    <main className="flex-1 overflow-y-auto custom-scrollbar px-6 py-8 md:px-10">
      <div className="mx-auto max-w-6xl space-y-7">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-[11px] font-mono font-bold uppercase tracking-[0.22em] text-primary-400">Team controls</p>
            <h1 className="text-2xl font-semibold text-white">Usage and monthly budget</h1>
            <p className="mt-2 max-w-2xl text-sm text-gray-400">Review estimated spend and active reservations for a team in the current UTC month.</p>
          </div>
          <button
            type="button"
            onClick={() => loadUsage()}
            disabled={busy || !usage}
            className="inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-gray-300 transition hover:border-white/20 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            <RefreshCw size={14} className={busy ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>

        <form
          onSubmit={(event) => { event.preventDefault(); loadUsage(); }}
          className="grid gap-4 rounded-2xl border border-white/10 bg-black/30 p-5 md:grid-cols-[1fr_1fr_auto] md:items-end"
        >
          <label className="space-y-2 text-xs text-gray-400">
            <span>Admin API key</span>
            <input
              type="password"
              autoComplete="off"
              value={adminKey}
              onChange={(event) => setAdminKey(event.target.value)}
              placeholder="Enter configured admin key"
              className="w-full rounded-lg border border-white/10 bg-black/50 px-3 py-2.5 font-mono text-sm text-white outline-none focus:border-primary-500"
            />
            <span className="block text-[11px] text-gray-600">Kept in this page only; it is not saved in browser storage.</span>
          </label>
          <label className="space-y-2 text-xs text-gray-400">
            <span>Team</span>
            <input
              value={teamName}
              onChange={(event) => setTeamName(event.target.value)}
              placeholder="e.g. research"
              className="w-full rounded-lg border border-white/10 bg-black/50 px-3 py-2.5 text-sm text-white outline-none focus:border-primary-500"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-primary-600 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-primary-500 disabled:opacity-50"
          >
            {busy ? 'Loading…' : 'Load usage'}
          </button>
        </form>

        {error && (
          <div role="alert" className="flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-200">
            <AlertCircle size={17} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {usage ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Metric icon={Wallet} label="Estimated spend" value={money(usage.spentUsd)} detail="Recorded this UTC month" />
              <Metric icon={Activity} label="Reserved" value={money(usage.reservedUsd)} detail="Active request reservations" />
              <Metric icon={Wallet} label="Budget remaining" value={money(usage.remainingUsd)} detail={usage.budgetUsd == null ? 'No monthly limit configured' : `of ${money(usage.budgetUsd)}`} />
              <Metric icon={Activity} label="Active gateway keys" value={keyCount ?? '—'} detail={`Team: ${usage.team}`} />
            </div>

            <section className="rounded-2xl border border-white/10 bg-black/30 p-5 md:p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-base font-semibold text-white">Monthly budget</h2>
                  <p className="mt-1 text-xs text-gray-500">Period starts {new Date(usage.period).toLocaleDateString()} · estimates use configured model prices</p>
                </div>
                <span className="rounded-full border border-white/10 px-3 py-1 text-[11px] font-mono text-gray-400">UTC calendar month</span>
              </div>
              {limit !== null && (
                <div className="mt-6">
                  <div className="mb-2 flex justify-between text-xs text-gray-400">
                    <span>{money(spent + reserved)} used or reserved</span>
                    <span>{money(limit)} limit</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/10">
                    <div className={`h-full rounded-full transition-all ${usedPercent >= 90 ? 'bg-red-400' : 'bg-primary-400'}`} style={{ width: `${usedPercent}%` }} />
                  </div>
                </div>
              )}
              <form onSubmit={saveBudget} className="mt-6 flex flex-col gap-3 border-t border-white/5 pt-5 sm:flex-row sm:items-end">
                <label className="flex-1 space-y-2 text-xs text-gray-400">
                  <span>Monthly limit in USD</span>
                  <input
                    type="number"
                    min="0"
                    step="0.000001"
                    value={budgetInput}
                    onChange={(event) => setBudgetInput(event.target.value)}
                    placeholder="Blank removes the limit"
                    className="w-full rounded-lg border border-white/10 bg-black/50 px-3 py-2.5 font-mono text-sm text-white outline-none focus:border-primary-500"
                  />
                </label>
                <button type="submit" disabled={busy} className="rounded-lg border border-primary-500/30 bg-primary-500/10 px-4 py-2.5 text-sm text-primary-300 transition hover:bg-primary-500/20 disabled:opacity-50">
                  Save budget
                </button>
              </form>
            </section>
          </>
        ) : (
          <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 px-6 py-16 text-center">
            <Wallet size={26} className="mx-auto text-gray-600" />
            <p className="mt-4 text-sm font-medium text-gray-300">Load a team to view its usage</p>
            <p className="mt-2 text-xs text-gray-600">The admin API must be enabled with `ADMIN_API_KEY` on the gateway.</p>
          </div>
        )}
        <p className="text-[11px] leading-relaxed text-gray-600">Spend is an estimate from the gateway’s configured model-price table, not a provider invoice. Reservations are included separately because request costs are reconciled after completion.</p>
      </div>
    </main>
  );
}

function Metric({ icon: Icon, label, value, detail }) {
  return (
    <article className="rounded-2xl border border-white/10 bg-black/30 p-5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500">{label}</span>
        <Icon size={16} className="text-primary-400" />
      </div>
      <p className="mt-4 font-mono text-2xl font-semibold tabular-nums text-white">{value}</p>
      <p className="mt-2 truncate text-[11px] text-gray-500">{detail}</p>
    </article>
  );
}
