export type BeforeInstallPromptEvent = Event & {
    prompt: () => Promise<void>;
    userChoice: Promise<{
        outcome: 'accepted' | 'dismissed';
        platform: string;
    }>;
};

const INSTALL_EVENT_NAME = 'pwa-install-availability-changed';

let deferredPrompt: BeforeInstallPromptEvent | null = null;
let initialized = false;

function notifyInstallStateChanged() {
    window.dispatchEvent(new Event(INSTALL_EVENT_NAME));
}

export function initPwaInstall() {
    if (initialized || typeof window === 'undefined') {
        return;
    }

    initialized = true;

    window.addEventListener('beforeinstallprompt', (event) => {
        event.preventDefault();

        deferredPrompt = event as BeforeInstallPromptEvent;
        notifyInstallStateChanged();
    });

    window.addEventListener('appinstalled', () => {
        deferredPrompt = null;
        notifyInstallStateChanged();
    });
}

export function hasPwaInstallPrompt(): boolean {
    return deferredPrompt !== null;
}

export async function showPwaInstallPrompt(): Promise<
    'accepted' | 'dismissed' | 'unavailable'
> {
    if (!deferredPrompt) {
        return 'unavailable';
    }

    const promptEvent = deferredPrompt;

    await promptEvent.prompt();

    const choice = await promptEvent.userChoice.catch(() => ({
        outcome: 'dismissed' as const,
        platform: '',
    }));

    // Hər quraşdırma hadisəsindən yalnız bir dəfə istifadə etmək olar.
    deferredPrompt = null;
    notifyInstallStateChanged();

    return choice.outcome;
}

export function subscribeToPwaInstallState(callback: () => void) {
    window.addEventListener(INSTALL_EVENT_NAME, callback);

    return () => {
        window.removeEventListener(INSTALL_EVENT_NAME, callback);
    };
}

export function isRunningAsInstalledPwa(): boolean {
    const navigatorWithStandalone = navigator as Navigator & {
        standalone?: boolean;
    };

    return (
        window.matchMedia('(display-mode: standalone)').matches ||
        navigatorWithStandalone.standalone === true
    );
}

export function isIosDevice(): boolean {
    return (
        /iPad|iPhone|iPod/i.test(navigator.userAgent) ||
        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
    );
}