interface CTAButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
}

export function CTAButton({ children, onClick }: CTAButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="bg-white ng-text-primary font-bold py-3 px-8 rounded hover:bg-gray-50 transition-colors text-lg"
    >
      {children}
    </button>
  );
}
