import { FormEvent, useState } from "react";
import { useSupabaseAuth } from "@/lib/useSupabaseAuth";
import VeyraRadar from "@/components/VeyraRadar";

const proofPoints = ["Deterministic detection", "AI explains, never decides", "Every delivery audited"];

export default function SupabaseLogin() {
  const { signIn, error: authError } = useSupabaseAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      await signIn(email.trim(), password);
    } catch {
      setMessage("Sign in failed. Check the account details and try again.");
    } finally {
      setBusy(false);
    }
  };

  const inputClass =
    "mt-2 h-11 w-full rounded-xl border-2 border-pine bg-white px-3 text-base font-medium text-pine outline-none placeholder:text-moss/60 focus:ring-4 focus:ring-pine/15";

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-sea text-pine">
      {/* One centred container: hero and card stay close together on any screen width */}
      <div className="mx-auto flex min-h-screen w-full max-w-[1200px] flex-col px-5 py-8 sm:px-10 lg:px-12 lg:py-12">
        <p className="text-center text-2xl font-extrabold tracking-[0.22em] lg:text-left">VEYRA</p>

        {/*
          Narrow screens: headline, sign-in card, radar (stacked, centred).
          Wide screens: headline + radar in the left column, card on the right.
        */}
        <div className="grid flex-1 content-center gap-10 py-10 lg:grid-cols-[minmax(0,1fr)_minmax(380px,460px)] lg:gap-x-20">
          {/* Headline */}
          <section className="flex flex-col items-center text-center lg:col-start-1 lg:row-start-1 lg:items-start lg:self-end lg:text-left">
            <h1 className="max-w-[540px] font-display text-4xl leading-[1.05] sm:text-5xl xl:text-6xl">
              Every alert, with its evidence.
            </h1>
            <p className="mt-5 max-w-[460px] text-base leading-relaxed text-moss sm:text-lg">
              Evidence-led monitoring for digital assets: detect, explain, escalate, and audit.
            </p>
            <ul className="mt-6 flex max-w-[540px] flex-wrap justify-center gap-2 lg:justify-start">
              {proofPoints.map((point) => (
                <li
                  key={point}
                  className="rounded-full border-2 border-pine bg-white px-3 py-1.5 font-mono text-xs font-medium uppercase tracking-wide"
                >
                  {point}
                </li>
              ))}
            </ul>
          </section>

          {/* Sign-in card */}
          <section className="flex w-full items-center justify-center lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:self-center">
            <div className="w-full max-w-md rounded-3xl border-2 border-pine bg-paper p-8 shadow-[8px_8px_0_var(--color-pine)] lg:max-w-none">
              <h2 className="font-display text-4xl leading-tight">Analyst sign in</h2>
              <p className="mt-2 text-sm leading-6 text-moss">
                Use your authorized account to access the hosted anomaly control plane.
              </p>

              <form onSubmit={submit} className="mt-7 space-y-4">
                <label className="block font-mono text-xs font-medium uppercase tracking-[0.1em]">
                  Email
                  <input
                    required
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className={inputClass}
                    autoComplete="email"
                    placeholder="name@company.com"
                  />
                </label>
                <label className="block font-mono text-xs font-medium uppercase tracking-[0.1em]">
                  Password
                  <input
                    required
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className={inputClass}
                    autoComplete="current-password"
                    placeholder="Your password"
                  />
                </label>
                {(message || authError) && (
                  <p role="alert" className="text-sm font-medium text-red-700">
                    {message ?? authError}
                  </p>
                )}
                <button
                  disabled={busy}
                  type="submit"
                  className="h-12 w-full rounded-xl border-2 border-pine bg-pine text-base font-bold text-mist transition hover:bg-moss disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {busy ? "Signing in…" : "Sign in"}
                </button>
              </form>

              <p className="mt-5 font-mono text-[11px] uppercase tracking-[0.08em] text-moss">
                Sessions are verified by the API on every request.
              </p>
            </div>
          </section>

          {/* Radar: smaller on narrow screens, full size on wide ones */}
          <div className="flex justify-center lg:col-start-1 lg:row-start-2 lg:justify-start lg:self-start">
            <VeyraRadar size={220} className="shrink-0 lg:hidden" />
            <VeyraRadar size={300} className="hidden shrink-0 lg:block" />
          </div>
        </div>
      </div>
    </main>
  );
}