import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Spinner } from "@/components/Spinner";
import { ErrorBanner } from "@/components/ErrorBanner";

interface SimulatorPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (transactionId: string) => void;
}

export function SimulatorPanel({
  isOpen,
  onClose,
  onSuccess,
}: SimulatorPanelProps) {
  const [presets, setPresets] = useState<
    {
      name: string;
      payload: { amount_inr: number; decline_reason: string };
    }[]
  >([]);
  const [loadingPresets, setLoadingPresets] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [simulating, setSimulating] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setLoadingPresets(true);
    setError(null);
    api
      .getDemoPresets()
      .then(setPresets)
      .catch((err) => setError(err.message || "Failed to load presets."))
      .finally(() => setLoadingPresets(false));
  }, [isOpen]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) {
      window.addEventListener("keydown", handleEsc);
    }
    return () => window.removeEventListener("keydown", handleEsc);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSimulate = async (
    preset: {
      name: string;
      payload: Record<string, unknown>;
    }
  ) => {
    setSimulating(preset.name);
    setError(null);
    try {
      const res = await api.simulateDemo(preset.payload);
      onSuccess(res.transaction_id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed.");
    } finally {
      setSimulating(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-sm">
      <div className="w-[400px] h-full bg-white shadow-xl flex flex-col animate-in slide-in-from-right duration-200">
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-200">
          <div>
            <h2 className="text-200 font-semibold text-slate-900 m-0">
              Simulate failure
            </h2>
            <p className="text-75 text-slate-500 m-0 mt-1">
              Test RECOVR with synthetic failed payments.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 border-none bg-transparent cursor-pointer p-2"
            aria-label="Close panel"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {error && <ErrorBanner message={error} />}

          {loadingPresets ? (
            <Spinner />
          ) : (
            <div className="flex flex-col gap-4">
              {presets.map((preset, i) => (
                <button
                  key={i}
                  onClick={() => handleSimulate(preset)}
                  disabled={!!simulating}
                  className="text-left border border-slate-200 rounded-md p-4 bg-white hover:border-brand hover:shadow-sm transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <strong className="block text-100 text-slate-900 mb-1">
                    {preset.name}
                  </strong>
                  <span className="block text-75 text-slate-500">
                    ₹{preset.payload.amount_inr} •{" "}
                    {preset.payload.decline_reason.replace(/_/g, " ")}
                  </span>
                  {simulating === preset.name && (
                    <div className="mt-3">
                      <Spinner />
                    </div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
