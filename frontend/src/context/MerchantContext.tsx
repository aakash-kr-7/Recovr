import { createContext, useContext, useState, ReactNode } from 'react';

interface MerchantContextType {
  merchantName: string | null;
  setMerchantName: (name: string | null) => void;
}

const MerchantContext = createContext<MerchantContextType | undefined>(undefined);

export function MerchantProvider({ children }: { children: ReactNode }) {
  const [merchantName, setMerchantName] = useState<string | null>(null);
  return (
    <MerchantContext.Provider value={{ merchantName, setMerchantName }}>
      {children}
    </MerchantContext.Provider>
  );
}

export function useMerchant() {
  const context = useContext(MerchantContext);
  if (context === undefined) {
    throw new Error('useMerchant must be used within a MerchantProvider');
  }
  return context;
}
